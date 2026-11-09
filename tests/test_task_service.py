import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mcp_gateway import MCPGateway, ToolRegistry
from backend.policy_engine import PolicyEngine, PolicyRepository
from backend.services import TaskService


def build_service(now_fn=None):
    repository = PolicyRepository.from_json(ROOT / "config" / "policies.json")
    engine = PolicyEngine(repository)
    service = TaskService(now_fn=now_fn) if now_fn else TaskService()
    registry = ToolRegistry()
    service.register_tools(registry)
    gateway = MCPGateway(engine, registry)
    service.bind_gateway(gateway)
    return service


class TaskServiceNormalTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_normal_task_completes_through_real_gateway(self):
        task = self.service.create_task("公益活动", "创建日程并通知参与者", "normal")
        self.assertEqual(task["status"], "COMPLETED")
        event_types = [event["event_type"] for event in task["events"]]
        self.assertIn("POLICY_DECISION", event_types)
        self.assertIn("TOOL_EXECUTED", event_types)
        decisions = [
            event for event in task["events"] if event["event_type"] == "POLICY_DECISION"
        ]
        for decision in decisions:
            self.assertIn("tool_request", decision["payload"])
        self.assertEqual(len(self.service.workspace.notifications), 1)

    def test_block_scenario_never_executes_malicious_request(self):
        task = self.service.create_task("可疑任务", "外部文档诱导", "block")
        self.assertEqual(task["status"], "BLOCKED")
        executed = [
            event for event in task["events"] if event["event_type"] == "TOOL_EXECUTED"
        ]
        for event in executed:
            self.assertNotEqual(
                event["payload"]["tool_request"]["tool_name"], "send_notice"
            )
        decisions = [
            event for event in task["events"] if event["event_type"] == "POLICY_DECISION"
        ]
        self.assertTrue(
            any(
                event["payload"]["decision"] == "BLOCK"
                and event["payload"]["risk_level"] == "CRITICAL"
                for event in decisions
            )
        )


class TaskServiceApprovalTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_approval_flow_approve_then_complete(self):
        task = self.service.create_task("群发通知", "40 人通知", "approval")
        self.assertEqual(task["status"], "WAITING_APPROVAL")
        approvals = self.service.list_approvals()
        self.assertEqual(len(approvals), 1)
        approval = approvals[0]
        self.assertEqual(approval["status"], "PENDING")
        self.assertIn("tool_request", approval)
        self.assertIn("reasons", approval)
        result = self.service.decide(approval["approval_id"], approved=True)
        self.assertEqual(result["status"], "APPROVED")
        task = self.service.task(str(task["task_id"]))
        self.assertEqual(task["status"], "COMPLETED")
        self.assertEqual(len(self.service.workspace.notifications), 1)

    def test_approval_flow_reject_keeps_tool_silent(self):
        task = self.service.create_task("群发通知", "40 人通知", "approval")
        approval = self.service.list_approvals()[0]
        result = self.service.decide(approval["approval_id"], approved=False)
        self.assertEqual(result["status"], "REJECTED")
        task = self.service.task(str(task["task_id"]))
        self.assertEqual(task["status"], "REJECTED")
        self.assertEqual(len(self.service.workspace.notifications), 0)

    def test_second_decision_is_rejected_as_conflict(self):
        task = self.service.create_task("群发通知", "40 人通知", "approval")
        approval = self.service.list_approvals()[0]
        self.service.decide(approval["approval_id"], approved=True)
        with self.assertRaises(PermissionError):
            self.service.decide(approval["approval_id"], approved=True)


class TaskServiceExpiryTests(unittest.TestCase):
    def test_expired_approval_marks_task_expired(self):
        clock = {"now": datetime.now(timezone.utc)}
        service = build_service(now_fn=lambda: clock["now"])
        task = service.create_task("群发通知", "40 人通知", "approval")
        approval = service.list_approvals()[0]
        clock["now"] = clock["now"] + timedelta(seconds=61)
        result = service.decide(approval["approval_id"], approved=True)
        self.assertEqual(result["status"], "EXPIRED")
        task = service.task(str(task["task_id"]))
        self.assertEqual(task["status"], "EXPIRED")
        event_types = [event["event_type"] for event in task["events"]]
        self.assertIn("APPROVAL_EXPIRED", event_types)
        self.assertEqual(len(service.workspace.notifications), 0)


class TaskServiceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()
        self.original = self.service.workspace.files["/workspace/activities/roster.csv"]

    def test_recovery_flow_restores_snapshot_after_circuit_break(self):
        task = self.service.create_task("文件更新", "更新共享排班", "recovery")
        self.assertEqual(task["status"], "WAITING_APPROVAL")
        approval = self.service.list_approvals()[0]
        self.service.decide(approval["approval_id"], approved=True)
        task = self.service.task(str(task["task_id"]))
        self.assertEqual(task["status"], "RECOVERED")
        event_types = [event["event_type"] for event in task["events"]]
        for required in (
            "TOOL_FAILED",
            "INCIDENT_TRIGGERED",
            "ACTION_CANCELLED",
            "SNAPSHOT_RESTORED",
            "RECOVERY_COMPLETED",
        ):
            self.assertIn(required, event_types)
        incidents = self.service.list_incidents()
        self.assertEqual(len(incidents), 1)
        incident = incidents[0]
        self.assertEqual(incident["status"], "RECOVERED")
        self.assertEqual(incident["before"], self.original)
        self.assertEqual(incident["after"], self.original)
        self.assertNotEqual(incident["damaged"], self.original)
        self.assertEqual(incident["cancelled_count"], 1)
        self.assertEqual(
            self.service.workspace.files["/workspace/activities/roster.csv"],
            self.original,
        )

    def test_invalid_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create_task("未知场景", "", "unknown")


if __name__ == "__main__":
    unittest.main()
