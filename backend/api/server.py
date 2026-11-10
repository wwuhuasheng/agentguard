"""FastAPI application exposing the core engine over the agreed HTTP contract.

Endpoints follow docs/INTEGRATION.md in the frontend console repository:
snake_case fields, timezone-aware ISO 8601 timestamps and no silent fallbacks.
The service is a demo runtime for the competition frontend; it keeps state in
memory and performs every policy decision through the real MCPGateway.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from re import fullmatch
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent_core import ActivitySpec
from backend.agent_core.agentarts_cloud import AgentArtsError, planner_from_env
from backend.api.app import create_app as create_core_app
from backend.mcp_gateway import MCPGateway, ToolRegistry
from backend.policy_engine import PolicyEngine, PolicyRepository
from backend.recovery import RecoveryController
from backend.services import DEMO_USER, TaskService

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


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    scenario: str = "normal"
    files: list[Dict[str, Any]] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    activity: Optional[ActivityInput] = None


class ApprovalDecision(BaseModel):
    decision: str
    comment: str = ""
    modified_arguments: Optional[Dict[str, Any]] = None


class TaskServiceRuntime:
    """Builds one shared in-memory runtime for the demo API."""

    def __init__(self) -> None:
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


def create_app() -> FastAPI:
    app = FastAPI(title="AgentGuard API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    runtime = TaskServiceRuntime()
    app.state.runtime = runtime
    service = runtime.service

    # One process and one enforcement gateway serve both the console contract
    # and the original task-coordinator API without route collisions.
    app.mount(
        "/core",
        create_core_app(gateway=runtime.gateway, expose_gateway_approval=False),
    )

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    def me() -> Dict[str, Any]:
        return dict(DEMO_USER)

    @app.get("/api/tasks")
    def tasks() -> list[Dict[str, Any]]:
        return service.list_tasks()

    @app.post("/api/tasks", status_code=201)
    def create_task(payload: TaskCreate) -> Dict[str, Any]:
        if payload.scenario == "activity":
            if not payload.description.strip():
                raise HTTPException(
                    status_code=422, detail="notice content is required"
                )
            if payload.activity is not None:
                starts_at = payload.activity.starts_at
                if starts_at.tzinfo is None or starts_at.utcoffset() is None:
                    raise HTTPException(status_code=422, detail="timezone is required")
                if starts_at <= datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=422, detail="activity time must be in the future"
                    )
                if not fullmatch(
                    r"[^@\s]+@[^@\s]+\.[^@\s]+", payload.activity.recipient
                ):
                    raise HTTPException(
                        status_code=422, detail="valid recipient email is required"
                    )
        try:
            return service.create_task(
                title=payload.title,
                description=payload.description,
                scenario=payload.scenario,
                files=payload.files,
                permissions=payload.permissions,
                activity=(
                    ActivitySpec(
                        title=payload.title,
                        starts_at=payload.activity.starts_at.isoformat(),
                        location=payload.activity.location,
                        recipient=payload.activity.recipient,
                        recipient_count=payload.activity.recipient_count,
                        notice_content=payload.description,
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
    def task(task_id: str) -> Dict[str, Any]:
        try:
            return service.task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None

    @app.get("/api/tasks/{task_id}/events")
    def task_events(task_id: str) -> list[Dict[str, Any]]:
        try:
            return service.task_events(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None

    @app.get("/api/approvals")
    def approvals() -> list[Dict[str, Any]]:
        return service.list_approvals()

    @app.post("/api/approvals/{approval_id}/decision")
    def decide(approval_id: str, payload: ApprovalDecision) -> Dict[str, Any]:
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
            return service.decide(approval_id, payload.decision == "APPROVE")
        except KeyError:
            raise HTTPException(status_code=404, detail="approval not found") from None
        except PermissionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/incidents")
    def incidents() -> list[Dict[str, Any]]:
        return service.list_incidents()

    @app.get("/api/incidents/{incident_id}")
    def incident(incident_id: str) -> Dict[str, Any]:
        try:
            return service.incident(incident_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="incident not found") from None

    return app


app = create_app()
