"""成员 C 首批接口回归测试。

对应 member-c-current-tasks.md 交付项 3,覆盖场景:
  1. 通知确认阈值边界(对应数据集 BND-01/BND-02/BND-03)
  2. 审批拒绝后无任何副作用(对应交接要求"审批拒绝后应是什么状态")
  3. 审批单次性、决策值校验与参数篡改防御(对应护照绑定"批准后不得换参数")

运行:python3 -m unittest tests.test_evaluation_regression -v
端点与请求结构已对照 backend/api/server.py 与 tests/test_integrated_api.py 核对。
"""

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.api.server import create_app


def future_start() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def activity_payload(recipient_count: int, update_shared_file: bool = False) -> dict:
    return {
        "title": "回归测试活动",
        "description": "活动提醒:请准时参加",
        "scenario": "activity",
        "activity": {
            "starts_at": future_start(),
            "location": "比赛会场",
            "recipient": "participants@example.org",
            "recipient_count": recipient_count,
            "update_shared_file": update_shared_file,
        },
    }


class ThresholdBoundaryRegressionTests(unittest.TestCase):
    """场景 1:confirmation_recipient_count=30 的两侧行为必须稳定。"""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_notice_below_threshold_completes_without_approval(self):
        """BND-02 对照:12 人(≤30)不应产生待审批,直接完成。"""
        created = self.client.post("/api/tasks", json=activity_payload(12))
        self.assertEqual(created.status_code, 201)
        task = created.json()
        self.assertEqual(task["status"], "COMPLETED")
        self.assertEqual(
            len(self.app.state.runtime.service.workspace.notifications), 1
        )
        self.assertEqual(self.app.state.runtime.service.list_approvals(), [])

    def test_threshold_is_strictly_greater_than_30(self):
        """BND-02:阈值语义为 recipient_count > 30(严格大于)。

        30 人 + 无文件更新 → 直接完成;31 人 → 进入确认。
        标注时曾因 update_shared_file 默认 True 的干扰误判,此处锁定语义。
        """
        created_30 = self.client.post("/api/tasks", json=activity_payload(30))
        self.assertEqual(created_30.status_code, 201)
        self.assertEqual(created_30.json()["status"], "COMPLETED")
        self.assertEqual(self.app.state.runtime.service.list_approvals(), [])
        self.assertEqual(
            len(self.app.state.runtime.service.workspace.notifications), 1
        )

    def test_default_file_update_confounds_threshold_reading(self):
        """边界误判防护:30 人 + 默认 update_shared_file=True 的
        WAITING_APPROVAL 来自文件更新步骤,不得误读为人数阈值。"""
        payload = activity_payload(30)
        payload["activity"].pop("update_shared_file")
        created = self.client.post("/api/tasks", json=payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["status"], "WAITING_APPROVAL")
        self.assertTrue(self.client.get("/api/approvals").json())
        self.assertEqual(
            self.app.state.runtime.service.workspace.notifications, []
        )

    def test_notice_above_threshold_waits_for_approval(self):
        """BND-01:40 人(>30)必须进入人工确认,批准前不得发送。"""
        created = self.client.post("/api/tasks", json=activity_payload(40))
        self.assertEqual(created.status_code, 201)
        task = created.json()
        self.assertEqual(task["status"], "WAITING_APPROVAL")
        self.assertEqual(
            self.app.state.runtime.service.workspace.notifications, [],
            "批准前不应存在任何发送记录",
        )


class ApprovalRejectRegressionTests(unittest.TestCase):
    """场景 2:REJECT 之后不得产生任何业务副作用。"""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_reject_leaves_no_notice_and_no_file_change(self):
        """BND-03 + 恢复语义:文件更新被拒绝后,文件必须保持原版本。"""
        before_files = dict(
            self.app.state.runtime.service.workspace.files
        )
        created = self.client.post(
            "/api/tasks", json=activity_payload(40, update_shared_file=True)
        )
        self.assertEqual(created.status_code, 201)
        task = created.json()
        self.assertEqual(task["status"], "WAITING_APPROVAL")

        approvals = self.client.get("/api/approvals").json()
        self.assertTrue(approvals, "40 人 + 文件更新应产生待审批项")
        for approval in approvals:
            resolved = self.client.post(
                f"/api/approvals/{approval['approval_id']}/decision",
                json={"decision": "REJECT"},
            )
            self.assertEqual(resolved.status_code, 200)

        workspace = self.app.state.runtime.service.workspace
        self.assertEqual(
            workspace.notifications, [], "拒绝后不应存在任何发送记录"
        )
        self.assertEqual(
            workspace.files,
            before_files,
            "文件更新被拒绝后必须保持原版本",
        )

    def test_rejected_approval_cannot_be_reapproved(self):
        """同一审批在 REJECT 之后不得再接受 APPROVE(单次性)。"""
        created = self.client.post("/api/tasks", json=activity_payload(40))
        self.assertEqual(created.status_code, 201)
        approval = self.client.get("/api/approvals").json()[0]
        url = f"/api/approvals/{approval['approval_id']}/decision"

        first = self.client.post(url, json={"decision": "REJECT"})
        self.assertEqual(first.status_code, 200)

        second = self.client.post(url, json={"decision": "APPROVE"})
        self.assertIn(
            second.status_code,
            (400, 404, 409, 410, 422),
            f"已拒绝的审批不应接受新的决策,实际返回 {second.status_code}",
        )
        self.assertEqual(
            self.app.state.runtime.service.workspace.notifications, []
        )


class ApprovalContractRegressionTests(unittest.TestCase):
    """场景 3:决策契约——非法值与参数篡改必须在接口层被拒。"""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        created = self.client.post("/api/tasks", json=activity_payload(40))
        self.assertEqual(created.status_code, 201)
        self.approval_url = (
            f"/api/approvals/"
            f"{self.client.get('/api/approvals').json()[0]['approval_id']}/decision"
        )

    def test_decision_value_is_validated(self):
        """小写/未知决策值应 422,不得静默当作 APPROVE。"""
        for bad in ("approve", "reject", "ALLOW", ""):
            response = self.client.post(
                self.approval_url, json={"decision": bad}
            )
            self.assertEqual(
                response.status_code,
                422,
                f"非法决策值 {bad!r} 应返回 422,实际 {response.status_code}",
            )

    def test_modified_arguments_are_rejected_not_applied(self):
        """批准时夹带修改参数:接口必须拒绝,防止批准后偷换参数。"""
        response = self.client.post(
            self.approval_url,
            json={
                "decision": "APPROVE",
                "modified_arguments": {"recipient": "attacker.invalid"},
            },
        )
        self.assertEqual(
            response.status_code,
            422,
            "modified_arguments 目前不受支持,必须显式拒绝",
        )
        self.assertEqual(
            self.app.state.runtime.service.workspace.notifications, []
        )


if __name__ == "__main__":
    unittest.main()
