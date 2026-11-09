from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from backend.models import AuditEvent, Decision, ExecutionResult, ToolRequest
from backend.policy_engine import PolicyEngine, approval_fingerprint
from backend.recovery import CircuitOpenError, RecoveryController

ToolHandler = Callable[[str, Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class PendingApproval:
    request: ToolRequest
    request_fingerprint: str
    expires_at: datetime


@dataclass
class ApprovedRetry:
    request: ToolRequest
    request_fingerprint: str
    remaining: int


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, tool_name: str, handler: ToolHandler) -> None:
        if tool_name in self._handlers:
            raise ValueError("tool already registered: {}".format(tool_name))
        self._handlers[tool_name] = handler

    def execute(self, request: ToolRequest) -> Dict[str, Any]:
        handler = self._handlers.get(request.tool_name)
        if handler is None:
            raise KeyError("tool not registered: {}".format(request.tool_name))
        return handler(request.action, request.arguments)


class MCPGateway:
    """The only component allowed to call registered tools."""

    def __init__(
        self,
        engine: PolicyEngine,
        registry: ToolRegistry,
        recovery: Optional[RecoveryController] = None,
        approval_ttl_seconds: int = 600,
        now_fn: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if approval_ttl_seconds < 1:
            raise ValueError("approval_ttl_seconds must be positive")
        self.engine = engine
        self.registry = registry
        self.recovery = recovery
        self.approval_ttl_seconds = approval_ttl_seconds
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.pending: Dict[str, PendingApproval] = {}
        self._approved_retries: Dict[str, ApprovedRetry] = {}
        self.audit_events: List[AuditEvent] = []

    def submit(self, request: ToolRequest) -> ExecutionResult:
        decision = self.engine.evaluate(request)
        self._record(request, "POLICY_DECISION", decision.to_dict())

        if decision.decision == Decision.BLOCK:
            return ExecutionResult(
                request.request_id,
                "BLOCKED",
                decision.decision,
                error="; ".join(reason.message for reason in decision.reasons),
            )

        if decision.decision == Decision.CONFIRM:
            fingerprint = approval_fingerprint(request)
            expires_at = self.now_fn() + timedelta(seconds=self.approval_ttl_seconds)
            self.pending[request.request_id] = PendingApproval(
                request=request,
                request_fingerprint=fingerprint,
                expires_at=expires_at,
            )
            self._record(
                request,
                "APPROVAL_REQUIRED",
                {
                    "status": "PENDING",
                    "request_fingerprint": fingerprint,
                    "expires_at": expires_at.isoformat(),
                    "preview": {
                        "tool_name": request.tool_name,
                        "action": request.action,
                        "argument_keys": sorted(request.arguments),
                    },
                },
            )
            return ExecutionResult(
                request.request_id,
                "PENDING_CONFIRMATION",
                decision.decision,
            )

        return self._execute(request, decision.decision)

    def resolve(self, request_id: str, approved: bool) -> ExecutionResult:
        pending = self.pending.pop(request_id, None)
        if pending is None:
            raise KeyError("pending request not found: {}".format(request_id))
        request = pending.request

        if self.now_fn() >= pending.expires_at:
            self._record(
                request,
                "APPROVAL_EXPIRED",
                {"expires_at": pending.expires_at.isoformat()},
            )
            return ExecutionResult(
                request.request_id,
                "APPROVAL_EXPIRED",
                Decision.CONFIRM,
                error="审批已过期，请重新发起任务。",
            )

        current_fingerprint = approval_fingerprint(request)
        if current_fingerprint != pending.request_fingerprint:
            self._record(
                request,
                "APPROVAL_INVALIDATED",
                {
                    "expected": pending.request_fingerprint,
                    "observed": current_fingerprint,
                },
            )
            return ExecutionResult(
                request.request_id,
                "APPROVAL_INVALIDATED",
                Decision.CONFIRM,
                error="请求内容发生变化，原审批已失效。",
            )

        self._record(
            request,
            "APPROVAL_RESOLVED",
            {
                "approved": approved,
                "request_fingerprint": pending.request_fingerprint,
            },
        )
        if not approved:
            return ExecutionResult(
                request.request_id,
                "REJECTED",
                Decision.CONFIRM,
                error="用户拒绝了该操作。",
            )
        result = self._execute(request, Decision.CONFIRM)
        if result.status in {"FAILED", "RESTORED"}:
            self._approved_retries[request_id] = ApprovedRetry(
                request, pending.request_fingerprint, remaining=2
            )
        return result

    def retry_approved(self, request_id: str) -> ExecutionResult:
        """Retry only the unchanged, previously approved request (at most twice)."""
        retry = self._approved_retries.get(request_id)
        if retry is None or retry.remaining < 1:
            raise PermissionError("no approved retry available")
        if approval_fingerprint(retry.request) != retry.request_fingerprint:
            self._approved_retries.pop(request_id, None)
            raise PermissionError("approved request changed")
        retry.remaining -= 1
        self._record(retry.request, "APPROVED_RETRY", {"remaining": retry.remaining})
        result = self._execute(retry.request, Decision.CONFIRM)
        if result.status == "SUCCEEDED" or retry.remaining == 0:
            self._approved_retries.pop(request_id, None)
        return result

    def _execute(self, request: ToolRequest, decision: Decision) -> ExecutionResult:
        try:
            if self.recovery:
                self.recovery.before_execute(request)
            output = self.registry.execute(request)
            if self.recovery:
                self.recovery.on_success(request)
            self._record(request, "TOOL_EXECUTED", {"output": output})
            return ExecutionResult(request.request_id, "SUCCEEDED", decision, output)
        except CircuitOpenError as exc:
            self._record(
                request,
                "CIRCUIT_REJECTED",
                {"tool_name": request.tool_name, "error": str(exc)},
            )
            return ExecutionResult(
                request.request_id,
                "CIRCUIT_OPEN",
                decision,
                error=str(exc),
            )
        except Exception as exc:  # boundary: tool failures become audit events
            incident = self.recovery.on_failure(request, exc) if self.recovery else None
            payload: Dict[str, Any] = {"error": str(exc)}
            if incident:
                payload["incident"] = incident.to_dict()
                self._record(
                    request,
                    "ROLLBACK_COMPLETED" if incident.restored else "ROLLBACK_SKIPPED",
                    incident.to_dict(),
                )
                if incident.circuit_opened:
                    self._record(
                        request,
                        "CIRCUIT_OPENED",
                        {"tool_name": request.tool_name},
                    )
            self._record(request, "TOOL_FAILED", payload)
            return ExecutionResult(
                request.request_id,
                "RESTORED" if incident and incident.restored else "FAILED",
                decision,
                error=str(exc),
            )

    def events_for_task(self, task_id: str) -> List[AuditEvent]:
        return [event for event in self.audit_events if event.task_id == task_id]

    def _record(
        self, request: ToolRequest, event_type: str, payload: Dict[str, Any]
    ) -> None:
        self.audit_events.append(
            AuditEvent(event_type, request.request_id, request.task_id, payload)
        )
