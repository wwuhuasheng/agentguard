from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.agent_core import (
    ActivitySpec,
    DeterministicAgentArtsAdapter,
    TaskCoordinator,
)
from backend.bootstrap import build_runtime
from backend.mcp_gateway import MCPGateway
from backend.models import TrustLevel


class ApprovalBody(BaseModel):
    approved: bool


class ActivityTaskBody(BaseModel):
    title: str = Field(min_length=1)
    starts_at: str = Field(min_length=1)
    location: str = Field(min_length=1)
    recipient: str = Field(min_length=3)
    recipient_count: int = Field(ge=1)
    notice_content: str = Field(min_length=1)
    source_trust: TrustLevel = TrustLevel.USER_CONFIRMED


def create_app(
    gateway: Optional[MCPGateway] = None,
    coordinator: Optional[TaskCoordinator] = None,
    expose_gateway_approval: bool = True,
) -> FastAPI:
    runtime_gateway = gateway or build_runtime()[0]
    runtime_coordinator = coordinator or TaskCoordinator(
        runtime_gateway, DeterministicAgentArtsAdapter()
    )
    app = FastAPI(
        title="御界 AgentGuard API",
        version="0.2.0",
        description="工具型智能体可信执行、审批、审计与恢复接口",
    )
    app.state.gateway = runtime_gateway
    app.state.coordinator = runtime_coordinator

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "service": "agentguard"}

    @app.post("/api/tasks")
    def create_task(body: ActivityTaskBody) -> Dict[str, Any]:
        task = runtime_coordinator.create_activity(
            ActivitySpec(
                title=body.title,
                starts_at=body.starts_at,
                location=body.location,
                recipient=body.recipient,
                recipient_count=body.recipient_count,
                notice_content=body.notice_content,
                source_trust=body.source_trust,
            )
        )
        return task.to_dict()

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> Dict[str, Any]:
        task = runtime_coordinator.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task.to_dict()

    @app.post("/api/tasks/{task_id}/decision")
    def resolve_task(task_id: str, body: ApprovalBody) -> Dict[str, Any]:
        try:
            return runtime_coordinator.resolve(task_id, body.approved).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> Dict[str, Any]:
        try:
            return runtime_coordinator.cancel(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    if expose_gateway_approval:

        @app.post("/api/approvals/{request_id}/decision")
        def resolve_approval(request_id: str, body: ApprovalBody) -> Dict[str, Any]:
            try:
                return runtime_gateway.resolve(request_id, body.approved).to_dict()
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/events")
    def task_events(task_id: str) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in runtime_gateway.events_for_task(task_id)]

    @app.get("/api/incidents/{incident_id}")
    def incident(incident_id: str) -> Dict[str, Any]:
        recovery = runtime_gateway.recovery
        value = recovery.get_incident(incident_id) if recovery else None
        if value is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return value.to_dict()

    @app.get("/api/runtime/circuits")
    def circuits() -> Dict[str, Dict[str, Any]]:
        if not runtime_gateway.recovery:
            return {}
        return runtime_gateway.recovery.breaker.states()

    return app


app = create_app()
