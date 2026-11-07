import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()

