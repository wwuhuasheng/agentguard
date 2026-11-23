"""FastAPI application exposing the core engine over the agreed HTTP contract.

Endpoints follow docs/INTEGRATION.md in the frontend console repository:
snake_case fields, timezone-aware ISO 8601 timestamps and no silent fallbacks.
The service is a demo runtime for the competition frontend; it keeps state in
memory and performs every policy decision through the real MCPGateway. Optional
visitor mode creates one independent runtime per browser session.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from re import fullmatch
from typing import Annotated, Any, Dict, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictBool

from backend.agent_core import ActivitySpec
from backend.agent_core.agentarts_cloud import AgentArtsError, planner_from_env
from backend.agent_core.permission_preview import preview_activity_permissions
from backend.api.app import create_app as create_core_app
from backend.api.demo_sessions import DemoSessionStore, SessionCapacityError
from backend.evidence import make_evidence_bundle
from backend.mcp_gateway import MCPGateway, ToolRegistry
from backend.policy_engine import PolicyEngine, PolicyRepository
from backend.recovery import RecoveryController
from backend.services import DEMO_USER, TaskService
from backend.source_ingest import (
    inspect_reference,
    review_reference_bundle,
    safe_bundle_signals,
)

_ROOT = Path(__file__).resolve().parents[2]
_POLICIES = _ROOT / "config" / "policies.json"

_ALLOW_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


class ActivityInput(BaseModel):
    starts_at: datetime
    location: str = Field(min_length=1, max_length=120)
    recipient: str = Field(min_length=3, max_length=254)
    recipient_count: int = Field(ge=1, le=1000)
    update_shared_file: StrictBool = True


class ReferenceInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=32768)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    scenario: str = "normal"
    files: list[Dict[str, Any]] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    activity: Optional[ActivityInput] = None
    reference: Optional[ReferenceInput] = None
    references: list[ReferenceInput] = Field(default_factory=list, max_length=2)
    schedule_preview_sha256: Optional[str] = None


class ActivityPreviewInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    activity: ActivityInput


class ReferencePreviewInput(BaseModel):
    reference: Optional[ReferenceInput] = None
    references: list[ReferenceInput] = Field(default_factory=list, max_length=2)
    recipient_count: int = Field(ge=1, le=1000)


def _reference_pairs(
    reference: Optional[ReferenceInput], references: list[ReferenceInput]
) -> list[tuple[str, str]]:
    if reference is not None and references:
        raise ValueError("use reference or references, not both")
    pairs = [(item.name, item.content) for item in references]
    if reference is not None:
        pairs = [(reference.name, reference.content)]
    if len(pairs) > 2:
        raise ValueError("at most two references are supported")
    return pairs


class ApprovalDecision(BaseModel):
    decision: str
    comment: str = ""
    modified_arguments: Optional[Dict[str, Any]] = None


class TaskServiceRuntime:
    """Build one in-memory policy, gateway and mock-tool runtime."""

    def __init__(self) -> None:
        self.visitor_id = str(uuid4())
        self.policy_sha256 = sha256(_POLICIES.read_bytes()).hexdigest()
        repository = PolicyRepository.from_json(_POLICIES)
        engine = PolicyEngine(repository)
        self.service = TaskService()
        registry = ToolRegistry()
        self.service.register_tools(registry)
        self.gateway = MCPGateway(
            engine,
            registry,
            recovery=RecoveryController(self.service.workspace),
            approval_ttl_seconds=60,
        )
        self.service.bind_gateway(self.gateway, planner_from_env())


def active_runtime(request: Request) -> TaskServiceRuntime:
    if request.app.state.isolated_sessions:
        return request.state.runtime
    runtime = request.app.state.runtime
    assert runtime is not None
    return runtime


def create_app(isolated_sessions: Optional[bool] = None) -> FastAPI:
    if isolated_sessions is None:
        isolated_sessions = os.getenv("AGENTGUARD_DEMO_ISOLATION") == "1"
    allowed_origins = _ALLOW_ORIGINS + [
        value.strip()
        for value in os.getenv("AGENTGUARD_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    ]
    app = FastAPI(title="AgentGuard API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    runtime = None if isolated_sessions else TaskServiceRuntime()
    app.state.runtime = runtime
    app.state.isolated_sessions = isolated_sessions
    app.state.sessions = (
        DemoSessionStore(TaskServiceRuntime) if isolated_sessions else None
    )

    if isolated_sessions:

        @app.middleware("http")
        async def visitor_session(request: Request, call_next):  # type: ignore[no-untyped-def]
            if (
                request.method == "OPTIONS"
                or request.url.path == "/api/health"
                or not request.url.path.startswith("/api/")
            ):
                return await call_next(request)
            origin = request.headers.get("origin")
            own_origin = f"{request.url.scheme}://{request.url.netloc}"
            if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and (
                origin not in allowed_origins and origin != own_origin
            ):
                return JSONResponse({"detail": "origin not allowed"}, status_code=403)
            try:
                session_id, visitor_runtime, _ = app.state.sessions.get_or_create(
                    request.cookies.get("agentguard_demo_session")
                )
            except SessionCapacityError:
                return JSONResponse(
                    {"detail": "demo visitor limit reached"}, status_code=503
                )
            request.state.runtime = visitor_runtime
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            response.set_cookie(
                "agentguard_demo_session",
                session_id,
                max_age=3600,
                path="/api",
                httponly=True,
                secure=(
                    request.url.scheme == "https"
                    or os.getenv("AGENTGUARD_SESSION_SECURE_COOKIE") == "1"
                ),
                samesite="lax",
            )
            return response

    # The developer mode keeps the original core API on the shared gateway.
    # Visitor mode omits it so no route can reach another session's gateway.
    if runtime is not None:
        app.mount(
            "/core",
            create_core_app(gateway=runtime.gateway, expose_gateway_approval=False),
        )

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    def me(
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        if isolated_sessions:
            return {
                **DEMO_USER,
                "user_id": runtime.visitor_id,
                "username": "demo-visitor",
                "display_name": "演示访客",
            }
        return dict(DEMO_USER)

    @app.get("/api/tasks")
    def tasks(
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> list[Dict[str, Any]]:
        return runtime.service.list_tasks()

    @app.post("/api/activities/preview")
    def preview_activity(
        payload: ActivityPreviewInput,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        activity = payload.activity
        _validate_activity_input(activity)
        try:
            return preview_activity_permissions(
                runtime.gateway.engine.repository,
                ActivitySpec(
                    title=payload.title,
                    starts_at=activity.starts_at.isoformat(),
                    location=activity.location,
                    recipient=activity.recipient,
                    recipient_count=activity.recipient_count,
                    notice_content=payload.description,
                    update_shared_file=activity.update_shared_file,
                ),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/activities/reference-preview")
    def preview_reference(payload: ReferencePreviewInput) -> Dict[str, Any]:
        try:
            return review_reference_bundle(
                _reference_pairs(payload.reference, payload.references),
                payload.recipient_count,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/tasks", status_code=201)
    def create_task(
        payload: TaskCreate,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        if (
            (payload.reference is not None or payload.references)
            and payload.scenario != "activity"
        ):
            raise HTTPException(
                status_code=422,
                detail="references are supported only for activity tasks",
            )
        if payload.scenario == "activity":
            if not payload.description.strip():
                raise HTTPException(
                    status_code=422, detail="notice content is required"
                )
            if payload.activity is not None:
                _validate_activity_input(payload.activity)
        try:
            pairs = _reference_pairs(payload.reference, payload.references)
            source_summaries = [
                inspect_reference(name, content) for name, content in pairs
            ]
            if len({x["format"] for x in source_summaries}) != len(source_summaries):
                raise ValueError("provide at most one TXT and one CSV")
            source_summary = source_summaries[0] if source_summaries else None
            csv_source = next(
                (
                    (name, content, summary)
                    for (name, content), summary in zip(pairs, source_summaries)
                    if summary["format"] == "csv"
                ),
                None,
            )
            schedule_assignments = ()
            if payload.schedule_preview_sha256 is not None:
                if (
                    payload.scenario != "activity"
                    or payload.activity is None
                    or not payload.activity.update_shared_file
                    or csv_source is None
                    or not fullmatch(r"[0-9a-f]{64}", payload.schedule_preview_sha256)
                    or csv_source[2]["sha256"] != payload.schedule_preview_sha256
                ):
                    raise ValueError(
                        "schedule adoption requires unchanged CSV and file permission"
                    )
                review = review_reference_bundle(
                    pairs,
                    payload.activity.recipient_count,
                )
                proposal = review["schedule_proposal"]
                if (
                    proposal is None
                    or proposal["unassigned_indices"]
                    or csv_source[2]["row_count"] != payload.activity.recipient_count
                    or len(proposal["assignments"]) != payload.activity.recipient_count
                ):
                    raise ValueError("schedule must cover every confirmed participant")
                schedule_assignments = tuple(
                    (item["candidate_index"], item["slot"])
                    for item in proposal["assignments"]
                )
            return runtime.service.create_task(
                title=payload.title,
                description=payload.description,
                scenario=payload.scenario,
                files=payload.files,
                permissions=payload.permissions,
                source_summary=source_summary,
                source_summaries=source_summaries,
                activity=(
                    ActivitySpec(
                        title=payload.title,
                        starts_at=payload.activity.starts_at.isoformat(),
                        location=payload.activity.location,
                        recipient=payload.activity.recipient,
                        recipient_count=payload.activity.recipient_count,
                        notice_content=payload.description,
                        update_shared_file=payload.activity.update_shared_file,
                        reference_signals=(
                            safe_bundle_signals(source_summaries)
                            if source_summaries
                            else None
                        ),
                        schedule_assignments=schedule_assignments,
                    )
                    if payload.activity is not None
                    else None
                ),
            )
        except AgentArtsError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/tasks/{task_id}")
    def task(
        task_id: str,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        try:
            return runtime.service.task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None

    @app.get("/api/tasks/{task_id}/events")
    def task_events(
        task_id: str,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> list[Dict[str, Any]]:
        try:
            return runtime.service.task_events(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None

    @app.get("/api/tasks/{task_id}/evidence")
    def task_evidence(
        task_id: str,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        try:
            return make_evidence_bundle(
                runtime.service.task(task_id), runtime.policy_sha256
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None

    @app.get("/api/approvals")
    def approvals(
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> list[Dict[str, Any]]:
        return runtime.service.list_approvals()

    @app.post("/api/approvals/{approval_id}/decision")
    def decide(
        approval_id: str,
        payload: ApprovalDecision,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        if payload.decision not in {"APPROVE", "REJECT"}:
            raise HTTPException(
                status_code=422, detail="decision must be APPROVE or REJECT"
            )
        if payload.modified_arguments is not None:
            raise HTTPException(
                status_code=422,
                detail="modified_arguments is not supported by the demo runtime yet",
            )
        try:
            return runtime.service.decide(approval_id, payload.decision == "APPROVE")
        except KeyError:
            raise HTTPException(status_code=404, detail="approval not found") from None
        except PermissionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/incidents")
    def incidents(
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> list[Dict[str, Any]]:
        return runtime.service.list_incidents()

    @app.get("/api/incidents/{incident_id}")
    def incident(
        incident_id: str,
        runtime: Annotated[TaskServiceRuntime, Depends(active_runtime)],
    ) -> Dict[str, Any]:
        try:
            return runtime.service.incident(incident_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="incident not found") from None

    return app


def _validate_activity_input(activity: ActivityInput) -> None:
    starts_at = activity.starts_at
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="timezone is required")
    if starts_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=422, detail="activity time must be in the future"
        )
    if not fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", activity.recipient):
        raise HTTPException(status_code=422, detail="valid recipient email is required")


app = create_app()
