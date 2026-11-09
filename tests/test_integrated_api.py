import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.api.server import create_app


def future_start() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


class IntegratedAPITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_console_and_core_share_one_gateway(self):
        console = self.client.post(
            "/api/tasks", json={"title": "社区活动", "scenario": "normal"}
        )
        self.assertEqual(console.status_code, 201)
        self.assertEqual(console.json()["status"], "COMPLETED")
        self.assertTrue(console.json()["passport_id"])

        core = self.client.post(
            "/core/api/tasks",
            json={
                "title": "志愿活动",
                "starts_at": future_start(),
                "location": "社区服务中心",
                "recipient": "participants@example.org",
                "recipient_count": 2,
                "notice_content": "活动提醒",
            },
        )
        self.assertEqual(core.status_code, 200)
        self.assertEqual(core.json()["status"], "WAITING_CONFIRMATION")
        resolved = self.client.post(
            f"/core/api/tasks/{core.json()['task_id']}/decision",
            json={"approved": True},
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "SUCCEEDED")
        core_app = next(route.app for route in self.app.routes if route.path == "/core")
        self.assertIs(self.app.state.runtime.gateway, core_app.state.gateway)
        self.assertEqual(len(self.app.state.runtime.service.workspace.notifications), 2)

    def test_unplanned_request_is_blocked_with_specific_evidence(self):
        result = self.client.post(
            "/api/tasks", json={"title": "可疑任务", "scenario": "block"}
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["status"], "BLOCKED")
        decisions = [
            event["payload"]
            for event in result.json()["events"]
            if event["event_type"] == "POLICY_DECISION"
            and event["payload"]["decision"] == "BLOCK"
        ]
        codes = {reason["code"] for reason in decisions[0]["reasons"]}
        self.assertIn("TASK_PASSPORT_VIOLATION", codes)
        self.assertIn("UNTRUSTED_SOURCE_ESCALATION", codes)
        self.assertIn("RECIPIENT_DOMAIN_DENIED", codes)
        self.assertIn("SENSITIVE_FIELDS_DENIED", codes)
        self.assertEqual(self.app.state.runtime.service.workspace.notifications, [])

    def test_recovery_retries_use_gateway_and_open_circuit(self):
        created = self.client.post(
            "/api/tasks", json={"title": "排班更新", "scenario": "recovery"}
        ).json()
        approval_id = self.client.get("/api/approvals").json()[0]["approval_id"]
        self.assertEqual(
            self.client.post(
                f"/api/approvals/{approval_id}/decision",
                json={"decision": "APPROVE"},
            ).status_code,
            200,
        )
        task = self.client.get(f"/api/tasks/{created['task_id']}").json()
        self.assertEqual(task["status"], "RECOVERED")
        events = [event["event_type"] for event in task["events"]]
        self.assertEqual(events.count("APPROVED_RETRY"), 2)
        self.assertIn("CIRCUIT_OPENED", events)
        self.assertTrue(
            self.app.state.runtime.gateway.recovery.breaker.states()["shared_file"][
                "is_open"
            ]
        )

    def test_core_cannot_resolve_console_approval_outside_service(self):
        self.client.post("/api/tasks", json={"title": "通知", "scenario": "approval"})
        approval_id = self.client.get("/api/approvals").json()[0]["approval_id"]
        response = self.client.post(
            f"/core/api/approvals/{approval_id}/decision", json={"approved": True}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.get("/api/approvals").json()[0]["status"], "PENDING"
        )

    def test_open_circuit_does_not_crash_next_recovery_task(self):
        for expected_status in ("RECOVERED", "FAILED"):
            task = self.client.post(
                "/api/tasks", json={"title": "排班更新", "scenario": "recovery"}
            ).json()
            approval_id = self.client.get("/api/approvals").json()[0]["approval_id"]
            response = self.client.post(
                f"/api/approvals/{approval_id}/decision",
                json={"decision": "APPROVE"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                self.client.get(f"/api/tasks/{task['task_id']}").json()["status"],
                expected_status,
            )

    def test_live_activity_uses_user_fields_and_resumes_after_approval(self):
        response = self.client.post(
            "/api/tasks",
            json={
                "title": "周末读书会",
                "description": "请提前到场签到",
                "scenario": "activity",
                "activity": {
                    "starts_at": future_start(),
                    "location": "社区图书馆",
                    "recipient": "readers@example.org",
                    "recipient_count": 12,
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        task = response.json()
        self.assertEqual(task["status"], "WAITING_APPROVAL")
        self.assertEqual(task["agent_plan"]["step_count"], 3)
        self.assertEqual(len(task["agent_plan"]["agent_evidence"]), 3)
        self.assertTrue(task["passport_id"])
        first_tool = next(
            e["payload"]["tool_request"]
            for e in task["events"]
            if e["event_type"] == "POLICY_DECISION"
        )
        self.assertEqual(first_tool["arguments"]["location"], "社区图书馆")
        approval = self.client.get("/api/approvals").json()[0]
        self.assertEqual(approval["tool_request"]["tool_name"], "shared_file")
        self.client.post(
            f"/api/approvals/{approval['approval_id']}/decision",
            json={"decision": "APPROVE"},
        )
        completed = self.client.get(f"/api/tasks/{task['task_id']}").json()
        self.assertEqual(completed["status"], "COMPLETED")
        notice = self.app.state.runtime.service.workspace.notifications[0]
        self.assertEqual(notice["recipient"], "readers@example.org")
        self.assertEqual(notice["content"], "请提前到场签到")

    def test_live_activity_bulk_notice_requires_second_approval(self):
        task = self.client.post(
            "/api/tasks",
            json={
                "title": "大型活动",
                "description": "活动提醒",
                "scenario": "activity",
                "activity": {
                    "starts_at": future_start(),
                    "location": "社区中心",
                    "recipient": "team@example.org",
                    "recipient_count": 40,
                },
            },
        ).json()
        first = self.client.get("/api/approvals").json()[0]
        self.client.post(
            f"/api/approvals/{first['approval_id']}/decision",
            json={"decision": "APPROVE"},
        )
        self.assertEqual(
            self.client.get(f"/api/tasks/{task['task_id']}").json()["status"],
            "WAITING_APPROVAL",
        )
        second = self.client.get("/api/approvals").json()[0]
        self.assertNotEqual(first["approval_id"], second["approval_id"])
        self.assertEqual(second["tool_request"]["tool_name"], "send_notice")
        self.client.post(
            f"/api/approvals/{second['approval_id']}/decision",
            json={"decision": "REJECT"},
        )
        self.assertEqual(
            self.client.get(f"/api/tasks/{task['task_id']}").json()["status"],
            "REJECTED",
        )
        self.assertEqual(self.app.state.runtime.service.workspace.notifications, [])
        self.assertEqual(self.app.state.runtime.service.workspace.calendar_events, [])
        self.assertEqual(
            self.app.state.runtime.service.workspace.files[
                "/workspace/activities/plan.md"
            ],
            "活动计划 v1",
        )

    def test_live_activity_requires_structured_parameters(self):
        missing = self.client.post(
            "/api/tasks", json={"title": "不完整任务", "scenario": "activity"}
        )
        self.assertEqual(missing.status_code, 422)
        naive = self.client.post(
            "/api/tasks",
            json={
                "title": "不完整任务",
                "scenario": "activity",
                "activity": {
                    "starts_at": future_start().split("+")[0],
                    "location": "社区中心",
                    "recipient": "team@example.org",
                    "recipient_count": 12,
                },
            },
        )
        self.assertEqual(naive.status_code, 422)

    def test_live_activity_disallowed_domain_is_blocked_before_notice(self):
        task = self.client.post(
            "/api/tasks",
            json={
                "title": "错误接收方",
                "description": "活动提醒",
                "scenario": "activity",
                "activity": {
                    "starts_at": future_start(),
                    "location": "社区中心",
                    "recipient": "outside@unapproved.example",
                    "recipient_count": 12,
                },
            },
        ).json()
        first = self.client.get("/api/approvals").json()[0]
        self.client.post(
            f"/api/approvals/{first['approval_id']}/decision",
            json={"decision": "APPROVE"},
        )
        result = self.client.get(f"/api/tasks/{task['task_id']}").json()
        self.assertEqual(result["status"], "BLOCKED")
        blocked = [
            event
            for event in result["events"]
            if event["event_type"] == "POLICY_DECISION"
            and event["payload"]["decision"] == "BLOCK"
        ]
        self.assertIn(
            "RECIPIENT_DOMAIN_DENIED",
            {reason["code"] for reason in blocked[0]["payload"]["reasons"]},
        )
        workspace = self.app.state.runtime.service.workspace
        self.assertEqual(workspace.notifications, [])
        self.assertEqual(workspace.calendar_events, [])


if __name__ == "__main__":
    unittest.main()
