import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mcp_gateway import MCPGateway, ToolRegistry
from backend.mock_tools import MockWorkspace, register_workspace_tools
from backend.models import Decision, ToolRequest, TrustLevel
from backend.policy_engine import PolicyEngine, PolicyRepository


class PolicyGatewayTests(unittest.TestCase):
    def setUp(self):
        repository = PolicyRepository.from_json(ROOT / "config" / "policies.json")
        registry = ToolRegistry()
        self.workspace = MockWorkspace()
        register_workspace_tools(registry, self.workspace)
        self.gateway = MCPGateway(PolicyEngine(repository), registry)

    def test_low_risk_calendar_action_is_allowed(self):
        request = ToolRequest(
            task_id="task-1",
            agent_id="activity-assistant",
            tool_name="calendar",
            action="create",
            arguments={"title": "活动", "starts_at": "2026-11-01T09:00:00"},
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        result = self.gateway.submit(request)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertEqual(len(self.workspace.calendar_events), 1)

    def test_bulk_notice_requires_confirmation(self):
        request = ToolRequest(
            task_id="task-2",
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "participants@example.org",
                "recipient_count": 40,
                "content": "活动通知",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        pending = self.gateway.submit(request)
        self.assertEqual(pending.status, "PENDING_CONFIRMATION")
        self.assertEqual(len(self.workspace.notifications), 0)

        completed = self.gateway.resolve(request.request_id, approved=True)
        self.assertEqual(completed.status, "SUCCEEDED")
        self.assertEqual(len(self.workspace.notifications), 1)

    def test_external_instruction_cannot_exfiltrate_sensitive_fields(self):
        request = ToolRequest(
            task_id="task-3",
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "attacker@outside.example",
                "recipient_count": 1,
                "content": "导出名单",
                "fields": ["name", "phone"],
            },
            source_trust=TrustLevel.EXTERNAL_UNTRUSTED,
        )
        result = self.gateway.submit(request)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertEqual(len(self.workspace.notifications), 0)

    def test_confirmed_file_update_is_not_blocked_on_windows(self):
        request = ToolRequest(
            task_id="task-5",
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={
                "path": "/workspace/activities/roster.csv",
                "content": "name,role\n用户A,待分配",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        result = self.gateway.submit(request)
        self.assertEqual(result.status, "PENDING_CONFIRMATION")
        self.assertEqual(result.decision, Decision.CONFIRM)

    def test_delete_is_denied_before_tool_execution(self):
        request = ToolRequest(
            task_id="task-4",
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="delete",
            arguments={"path": "/workspace/activities/roster.csv"},
            source_trust=TrustLevel.EXTERNAL_UNTRUSTED,
        )
        result = self.gateway.submit(request)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("/workspace/activities/roster.csv", self.workspace.files)

    def test_sibling_path_cannot_bypass_allowed_directory(self):
        request = ToolRequest(
            task_id="task-path-boundary",
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="read",
            arguments={"path": "/workspace/activities_evil/secret.txt"},
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        result = self.gateway.submit(request)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.decision, Decision.BLOCK)

    def test_expired_approval_cannot_execute(self):
        current_time = [datetime(2026, 10, 28, tzinfo=timezone.utc)]
        repository = PolicyRepository.from_json(ROOT / "config" / "policies.json")
        registry = ToolRegistry()
        workspace = MockWorkspace()
        register_workspace_tools(registry, workspace)
        gateway = MCPGateway(
            PolicyEngine(repository),
            registry,
            approval_ttl_seconds=10,
            now_fn=lambda: current_time[0],
        )
        request = ToolRequest(
            task_id="task-expired-approval",
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={
                "path": "/workspace/activities/plan.md",
                "content": "不得写入",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        pending = gateway.submit(request)
        self.assertEqual(pending.status, "PENDING_CONFIRMATION")
        current_time[0] += timedelta(seconds=11)

        result = gateway.resolve(request.request_id, approved=True)
        self.assertEqual(result.status, "APPROVAL_EXPIRED")
        self.assertNotEqual(
            workspace.files["/workspace/activities/plan.md"], "不得写入"
        )

    def test_changed_parameters_invalidate_existing_approval(self):
        request = ToolRequest(
            task_id="task-approval-binding",
            agent_id="activity-assistant",
            tool_name="shared_file",
            action="update",
            arguments={
                "path": "/workspace/activities/plan.md",
                "content": "用户预览的内容",
            },
            source_trust=TrustLevel.USER_CONFIRMED,
        )
        pending = self.gateway.submit(request)
        self.assertEqual(pending.status, "PENDING_CONFIRMATION")

        request.arguments["content"] = "审批后被替换的内容"
        result = self.gateway.resolve(request.request_id, approved=True)

        self.assertEqual(result.status, "APPROVAL_INVALIDATED")
        self.assertNotEqual(
            self.workspace.files["/workspace/activities/plan.md"],
            "审批后被替换的内容",
        )


if __name__ == "__main__":
    unittest.main()
