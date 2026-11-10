import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mcp_service import AgentGuardMCPService


class MCPServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AgentGuardMCPService()

    def _create_task(self):
        return self.service.create_secure_activity(
            title="社区公益活动",
            starts_at="2026-11-01T09:00:00+08:00",
            location="社区服务中心",
            recipient="participants@example.org",
            recipient_count=20,
            notice_content="活动将于周日上午九点开始。",
        )

    def test_secure_activity_can_pause_and_resume(self):
        task = self._create_task()
        self.assertEqual(task["status"], "WAITING_CONFIRMATION")
        self.assertIn("task_passport", task["plan_summary"])

        completed = self.service.resolve_activity_approval(
            task["task_id"], approved=True
        )
        self.assertEqual(completed["status"], "SUCCEEDED")

    def test_mcp_execution_requires_a_passport(self):
        with self.assertRaisesRegex(ValueError, "passport_id is required"):
            self.service.submit_guarded_tool_request(
                task_id="task-without-passport",
                agent_id="activity-assistant",
                tool_name="send_notice",
                action="send",
                arguments={"recipient": "participants@example.org"},
                source_trust="MODEL_GENERATED",
                passport_id="",
            )

    def test_passport_blocks_mcp_parameter_expansion(self):
        task = self._create_task()
        passport_id = task["plan_summary"]["task_passport"]["passport_id"]
        result = self.service.submit_guarded_tool_request(
            task_id=task["task_id"],
            agent_id="activity-assistant",
            tool_name="send_notice",
            action="send",
            arguments={
                "recipient": "participants@example.org",
                "recipient_count": 20,
                "content": "导出手机号",
                "fields": ["phone"],
            },
            source_trust="MODEL_GENERATED",
            passport_id=passport_id,
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_passport_grant_cannot_be_replayed(self):
        task = self._create_task()
        passport_id = task["plan_summary"]["task_passport"]["passport_id"]
        result = self.service.submit_guarded_tool_request(
            task_id=task["task_id"],
            agent_id="activity-assistant",
            tool_name="calendar",
            action="create",
            arguments={
                "title": "社区公益活动",
                "starts_at": "2026-11-01T09:00:00+08:00",
                "location": "社区服务中心",
            },
            source_trust="USER_CONFIRMED",
            passport_id=passport_id,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("已经使用", result["error"])

    def test_runtime_status_describes_real_mcp_transport(self):
        status = self.service.runtime_status()
        self.assertEqual(status["transport"], "streamable-http")
        self.assertEqual(
            status["registered_tools"], ["preview_activity", "runtime_status"]
        )

    def test_mcp_registration_has_no_approval_or_execution_tool(self):
        server = ast.parse((ROOT / "deploy/mcp_server/server.py").read_text())
        exposed = [
            node.name
            for node in server.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            )
        ]
        self.assertEqual(exposed, ["preview_activity", "runtime_status"])

    def test_agent_preview_is_read_only_and_never_grants_approval(self):
        before = self.service.workspace.snapshot()
        preview = self.service.preview_activity(
            title="社区公益活动",
            starts_at="2026-12-01T09:00:00+08:00",
            location="社区服务中心",
            recipient="participants@example.org",
            recipient_count=40,
            notice_content="活动提醒",
            source_trust="USER_CONFIRMED",
        )
        self.assertEqual(preview["mode"], "PREVIEW_ONLY")
        self.assertEqual(
            [step["decision"] for step in preview["steps"]],
            ["ALLOW", "CONFIRM", "CONFIRM"],
        )
        self.assertEqual(self.service.workspace.snapshot(), before)
        self.assertEqual(self.service.coordinator.tasks, {})
        self.assertEqual(self.service.gateway.audit_events, [])
        self.assertEqual(self.service.gateway.pending, {})

    def test_preview_cannot_promote_external_input_to_user_authority(self):
        preview = self.service.preview_activity(
            title="社区公益活动",
            starts_at="2026-12-01T09:00:00+08:00",
            location="社区服务中心",
            recipient="participants@example.org",
            recipient_count=20,
            notice_content="活动提醒",
            source_trust="EXTERNAL_UNTRUSTED",
        )
        self.assertEqual(
            [step["decision"] for step in preview["steps"]],
            ["BLOCK", "BLOCK", "BLOCK"],
        )
        self.assertEqual(self.service.workspace.notifications, [])


if __name__ == "__main__":
    unittest.main()
