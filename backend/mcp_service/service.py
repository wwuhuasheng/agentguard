from __future__ import annotations

from typing import Any, Dict

from backend.agent_core import (
    ActivitySpec,
    DeterministicAgentArtsAdapter,
    TaskCoordinator,
)
from backend.agent_core.permission_preview import preview_activity_permissions
from backend.bootstrap import build_runtime
from backend.models import ToolRequest, TrustLevel


class AgentGuardMCPService:
    """Protocol-independent tool facade exposed by the real MCP server."""

    def __init__(self) -> None:
        self.gateway, self.workspace = build_runtime()
        self.coordinator = TaskCoordinator(
            self.gateway, DeterministicAgentArtsAdapter()
        )

    def preview_activity(
        self,
        title: str,
        starts_at: str,
        location: str,
        recipient: str,
        recipient_count: int,
        notice_content: str,
        source_trust: str = "MODEL_GENERATED",
        update_shared_file: bool = True,
    ) -> Dict[str, Any]:
        """Assess a hypothetical plan without touching live tasks or tools.

        The caller-supplied trust label is a preview assumption, never a grant of
        authority. A fresh policy engine and passport registry isolate the
        one-use evaluation from the live execution gateway.
        """
        spec = ActivitySpec(
            title=title,
            starts_at=starts_at,
            location=location,
            recipient=recipient,
            recipient_count=recipient_count,
            notice_content=notice_content,
            source_trust=self._trust_level(source_trust),
            update_shared_file=update_shared_file,
        )
        return preview_activity_permissions(self.gateway.engine.repository, spec)

    def create_secure_activity(
        self,
        title: str,
        starts_at: str,
        location: str,
        recipient: str,
        recipient_count: int,
        notice_content: str,
        source_trust: str = "USER_CONFIRMED",
    ) -> Dict[str, Any]:
        spec = ActivitySpec(
            title=title,
            starts_at=starts_at,
            location=location,
            recipient=recipient,
            recipient_count=recipient_count,
            notice_content=notice_content,
            source_trust=self._trust_level(source_trust),
        )
        return self.coordinator.create_activity(spec).to_dict()

    def resolve_activity_approval(self, task_id: str, approved: bool) -> Dict[str, Any]:
        return self.coordinator.resolve(task_id, approved).to_dict()

    def cancel_activity_task(self, task_id: str) -> Dict[str, Any]:
        return self.coordinator.cancel(task_id).to_dict()

    def get_activity_task(self, task_id: str) -> Dict[str, Any]:
        task = self.coordinator.get(task_id)
        if task is None:
            raise ValueError("task not found: {}".format(task_id))
        return task.to_dict()

    def get_task_trace(self, task_id: str) -> Dict[str, Any]:
        task = self.coordinator.get(task_id)
        return {
            "task": task.to_dict() if task else None,
            "events": [
                event.to_dict() for event in self.gateway.events_for_task(task_id)
            ],
        }

    def submit_guarded_tool_request(
        self,
        task_id: str,
        agent_id: str,
        tool_name: str,
        action: str,
        arguments: Dict[str, Any],
        source_trust: str,
        passport_id: str,
    ) -> Dict[str, Any]:
        """Submit an exact passport-bound request; raw tools are never exposed."""

        if not passport_id:
            raise ValueError("passport_id is required for MCP tool execution")
        request = ToolRequest(
            task_id=task_id,
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            arguments=arguments,
            source_trust=self._trust_level(source_trust),
            passport_id=passport_id,
        )
        return self.gateway.submit(request).to_dict()

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "service": "agentguard-mcp",
            "status": "ok",
            "transport": "streamable-http",
            "policy_mode": "deterministic",
            "registered_tools": [
                "preview_activity",
                "runtime_status",
            ],
            "circuits": self.gateway.recovery.breaker.states()
            if self.gateway.recovery
            else {},
        }

    @staticmethod
    def _trust_level(value: str) -> TrustLevel:
        try:
            return TrustLevel(value)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in TrustLevel)
            raise ValueError(
                "invalid source_trust; expected one of: {}".format(allowed)
            ) from exc
