import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agent_core import (
    ActivitySpec,
    DeterministicAgentArtsAdapter,
    TaskCoordinator,
)
from backend.bootstrap import build_runtime
from backend.models import TaskStatus, ToolRequest, TrustLevel


class TaskCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.gateway, self.workspace = build_runtime()
        self.coordinator = TaskCoordinator(
            self.gateway, DeterministicAgentArtsAdapter()
        )

    @staticmethod
    def _spec(source_trust=TrustLevel.USER_CONFIRMED):
        return ActivitySpec(
            title="社区公益活动",
            starts_at="2026-11-01T09:00:00+08:00",
            location="社区服务中心",
            recipient="participants@example.org",
            recipient_count=20,
            notice_content="活动将于周日上午九点开始。",
            source_trust=source_trust,
        )

    def test_transaction_pauses_and_resumes_after_confirmation(self):
        task = self.coordinator.create_activity(self._spec())
        self.assertEqual(task.status, TaskStatus.WAITING_CONFIRMATION)
        self.assertEqual(task.current_step, 1)
        self.assertEqual(len(self.workspace.calendar_events), 1)

        completed = self.coordinator.resolve(task.task_id, approved=True)
        self.assertEqual(completed.status, TaskStatus.SUCCEEDED)
        self.assertEqual(completed.current_step, 3)
        self.assertEqual(len(self.workspace.notifications), 1)
        self.assertIn(
            "社区公益活动", self.workspace.files["/workspace/activities/plan.md"]
        )

    def test_rejection_restores_whole_transaction(self):
        original = self.workspace.snapshot()
        task = self.coordinator.create_activity(self._spec())
        cancelled = self.coordinator.resolve(task.task_id, approved=False)

        self.assertEqual(cancelled.status, TaskStatus.CANCELLED)
        self.assertEqual(self.workspace.snapshot(), original)

    def test_untrusted_input_is_blocked_before_side_effects(self):
        original = self.workspace.snapshot()
        task = self.coordinator.create_activity(
            self._spec(TrustLevel.EXTERNAL_UNTRUSTED)
        )

        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertEqual(self.workspace.snapshot(), original)

    def test_plan_exposes_three_agent_evidence_records(self):
        task = self.coordinator.create_activity(self._spec())
        evidence = task.plan_summary["agent_evidence"]
        self.assertEqual(len(evidence), 3)
        self.assertEqual(
            {item["role"] for item in evidence},
            {
                "BUSINESS_AGENT",
                "CONTENT_ISOLATION_AGENT",
                "BEHAVIOR_GUARD_AGENT",
            },
        )

    def test_task_passport_blocks_unplanned_parameter_expansion(self):
        task = self.coordinator.create_activity(self._spec())
        passport = task.plan_summary["task_passport"]
        expanded_request = ToolRequest(
            task_id=task.task_id,
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "participants@example.org",
                "recipient_count": 20,
                "content": "活动通知",
                "fields": ["phone"],
            },
            source_trust=TrustLevel.USER_CONFIRMED,
            passport_id=passport["passport_id"],
        )

        result = self.gateway.submit(expanded_request)
        self.assertEqual(result.status, "BLOCKED")
        decision_event = self.gateway.audit_events[-1]
        self.assertEqual(
            decision_event.payload["reasons"][0]["code"],
            "TASK_PASSPORT_VIOLATION",
        )

    def test_user_can_exclude_file_update_and_passport_blocks_adding_it_back(self):
        spec = self._spec()
        spec = ActivitySpec(**{**spec.__dict__, "update_shared_file": False})
        original_files = dict(self.workspace.files)
        task = self.coordinator.create_activity(spec)
        self.assertEqual(task.status, TaskStatus.SUCCEEDED)
        self.assertEqual(task.total_steps, 2)
        self.assertEqual(
            [step["tool_name"] for step in task.plan_summary["steps"]],
            ["calendar", "send_notice"],
        )
        self.assertEqual(self.workspace.files, original_files)
        self.assertEqual(len(self.workspace.notifications), 1)
        unauthorized = ToolRequest(
            task_id=task.task_id,
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={"path": "/workspace/activities/plan.md", "content": "越权"},
            source_trust=TrustLevel.USER_CONFIRMED,
            passport_id=task.plan_summary["task_passport"]["passport_id"],
        )
        result = self.gateway.submit(unauthorized)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(
            self.gateway.audit_events[-1].payload["reasons"][0]["code"],
            "TASK_PASSPORT_VIOLATION",
        )
        self.assertEqual(self.workspace.files, original_files)


if __name__ == "__main__":
    unittest.main()
