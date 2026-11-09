import unittest

from fastapi.testclient import TestClient

from backend.api.server import create_app


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
                "starts_at": "2026-11-10T09:00:00+08:00",
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


if __name__ == "__main__":
    unittest.main()
