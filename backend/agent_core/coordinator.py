from __future__ import annotations

from typing import Dict, Optional

from backend.agent_core.contracts import (
    ActivitySpec,
    OrchestrationPlan,
    PlanningAdapter,
)
from backend.mcp_gateway import MCPGateway
from backend.models import ExecutionResult, TaskRecord, TaskStatus
from backend.policy_engine import PassportIssuer


class TaskCoordinator:
    """Runs a plan as a resumable transaction around the MCP gateway."""

    def __init__(self, gateway: MCPGateway, planner: PlanningAdapter) -> None:
        self.gateway = gateway
        self.planner = planner
        self.passport_issuer = PassportIssuer(gateway.engine.passports)
        self.tasks: Dict[str, TaskRecord] = {}
        self._plans: Dict[str, OrchestrationPlan] = {}

    def create_activity(
        self, spec: ActivitySpec, task_id: Optional[str] = None
    ) -> TaskRecord:
        placeholder = TaskRecord(
            intent="CREATE_ACTIVITY",
            status=TaskStatus.CREATED,
            total_steps=0,
            **({"task_id": task_id} if task_id else {}),
        )
        plan = self.planner.plan_activity(placeholder.task_id, spec)
        passport, bound_steps = self.passport_issuer.issue(
            placeholder.task_id, plan.steps
        )
        plan = OrchestrationPlan(
            task_id=plan.task_id,
            steps=bound_steps,
            evidence=plan.evidence,
            provider=plan.provider,
        )
        placeholder.total_steps = len(plan.steps)
        placeholder.plan_summary = plan.summary()
        placeholder.plan_summary["task_passport"] = passport.to_dict()
        self.tasks[placeholder.task_id] = placeholder
        self._plans[placeholder.task_id] = plan
        if self.gateway.recovery:
            self.gateway.recovery.begin_task(placeholder.task_id)
        return self._run(placeholder)

    def get(self, task_id: str) -> Optional[TaskRecord]:
        return self.tasks.get(task_id)

    def requests_for(self, task_id: str):
        """Return the exact authorized requests for presentation/audit adapters."""
        return tuple(self._plans[task_id].steps)

    def resolve(self, task_id: str, approved: bool) -> TaskRecord:
        task = self._require_waiting_task(task_id)
        request_id = task.pending_request_id
        result = self.gateway.resolve(request_id, approved)
        task.pending_request_id = None
        task.results.append(result.to_dict())
        if not approved:
            task.status = TaskStatus.CANCELLED
            self._restore_task(task)
            task.touch()
            return task
        if not self._accept_result(task, result):
            return task
        task.current_step += 1
        return self._run(task)

    def cancel(self, task_id: str) -> TaskRecord:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError("task not found: {}".format(task_id))
        if task.status == TaskStatus.WAITING_CONFIRMATION and task.pending_request_id:
            result = self.gateway.resolve(task.pending_request_id, approved=False)
            task.results.append(result.to_dict())
            task.pending_request_id = None
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.CANCELLED}:
            raise ValueError(
                "task cannot be cancelled from {}".format(task.status.value)
            )
        task.status = TaskStatus.CANCELLED
        self._restore_task(task)
        task.touch()
        return task

    def _run(self, task: TaskRecord) -> TaskRecord:
        plan = self._plans[task.task_id]
        task.status = TaskStatus.RUNNING
        task.touch()
        while task.current_step < task.total_steps:
            request = plan.steps[task.current_step]
            result = self.gateway.submit(request)
            if result.status == "PENDING_CONFIRMATION":
                task.status = TaskStatus.WAITING_CONFIRMATION
                task.pending_request_id = request.request_id
                task.touch()
                return task
            task.results.append(result.to_dict())
            if not self._accept_result(task, result):
                return task
            task.current_step += 1
        task.status = TaskStatus.SUCCEEDED
        if self.gateway.recovery:
            self.gateway.recovery.complete_task(task.task_id)
        task.touch()
        return task

    def _accept_result(self, task: TaskRecord, result: ExecutionResult) -> bool:
        if result.status == "SUCCEEDED":
            return True
        if result.status == "BLOCKED":
            task.status = TaskStatus.BLOCKED
        elif result.status == "RESTORED":
            task.status = TaskStatus.RESTORED
        else:
            task.status = TaskStatus.FAILED
        self._restore_task(task)
        task.touch()
        return False

    def _restore_task(self, task: TaskRecord) -> None:
        if self.gateway.recovery:
            self.gateway.recovery.restore_task(task.task_id)

    def _require_waiting_task(self, task_id: str) -> TaskRecord:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError("task not found: {}".format(task_id))
        if (
            task.status != TaskStatus.WAITING_CONFIRMATION
            or not task.pending_request_id
        ):
            raise ValueError("task is not waiting for confirmation")
        return task
