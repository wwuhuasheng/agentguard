from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.api.server import create_app


def activity_payload(*, count=12, update_file=True):
    return {
        "title": "社区活动",
        "description": "请在活动前十分钟到场",
        "scenario": "activity",
        "activity": {
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "location": "社区中心",
            "recipient": "volunteers@example.org",
            "recipient_count": count,
            "update_shared_file": update_file,
        },
    }


def test_file_approval_shows_diff_and_rejects_stale_target_without_rollback():
    app = create_app()
    client = TestClient(app)
    created = client.post("/api/tasks", json=activity_payload())
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    approval = client.get("/api/approvals").json()[0]
    impact = approval["impact_preview"]
    assert impact["kind"] == "FILE_UPDATE"
    assert impact["before_sha256"]
    assert impact["proposed_sha256"] != impact["before_sha256"]
    assert "--- 当前模拟文件" in impact["diff"]
    assert "+" in impact["diff"]

    workspace = app.state.runtime.service.workspace
    path = impact["path"]
    workspace.files[path] = "另一任务刚更新的版本"
    result = client.post(
        f"/api/approvals/{approval['approval_id']}/decision",
        json={"decision": "APPROVE"},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "INVALIDATED"
    assert result.json()["invalidation_code"] == "TARGET_CHANGED"
    assert workspace.files[path] == "另一任务刚更新的版本"
    assert workspace.notifications == []
    assert len(workspace.calendar_events) == 1
    assert app.state.runtime.gateway.pending == {}
    task = client.get(f"/api/tasks/{task_id}").json()
    assert task["status"] == "CANCELLED"
    event_types = [event["event_type"] for event in task["events"]]
    assert "APPROVAL_INVALIDATED" in event_types
    assert "PARTIAL_EFFECT_RETAINED" in event_types
    assert client.get(f"/api/tasks/{task_id}/evidence").json()["verification"]["ok"]


def test_unrelated_file_change_does_not_invalidate_target_approval():
    app = create_app()
    client = TestClient(app)
    client.post("/api/tasks", json=activity_payload())
    approval = client.get("/api/approvals").json()[0]
    workspace = app.state.runtime.service.workspace
    workspace.files["/workspace/activities/roster.csv"] = "无关文件的新版本"
    result = client.post(
        f"/api/approvals/{approval['approval_id']}/decision",
        json={"decision": "APPROVE"},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "APPROVED"
    assert workspace.files["/workspace/activities/roster.csv"] == "无关文件的新版本"
    assert workspace.files["/workspace/activities/plan.md"] != "活动计划 v1"


def test_notice_impact_preview_names_scope_without_sending_before_approval():
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/tasks", json=activity_payload(count=40, update_file=False)
    )
    assert created.status_code == 201
    approval = client.get("/api/approvals").json()[0]
    impact = approval["impact_preview"]
    assert impact["kind"] == "NOTICE_SEND"
    assert impact["recipient"] == "volunteers@example.org"
    assert impact["recipient_count"] == 40
    assert impact["content_sha256"]
    assert app.state.runtime.service.workspace.notifications == []


def test_stale_recovery_approval_does_not_arm_next_file_update_failure():
    app = create_app()
    client = TestClient(app)
    recovery = client.post(
        "/api/tasks", json={"title": "恢复演示", "scenario": "recovery"}
    )
    assert recovery.status_code == 201
    old_approval = client.get("/api/approvals").json()[0]
    workspace = app.state.runtime.service.workspace
    workspace.files["/workspace/activities/roster.csv"] = "其他任务的更新"
    stale = client.post(
        f"/api/approvals/{old_approval['approval_id']}/decision",
        json={"decision": "APPROVE"},
    )
    assert stale.json()["status"] == "INVALIDATED"
    assert workspace.files["/workspace/activities/roster.csv"] == "其他任务的更新"

    next_task = client.post("/api/tasks", json=activity_payload())
    assert next_task.status_code == 201
    current_approval = client.get("/api/approvals").json()[0]
    result = client.post(
        f"/api/approvals/{current_approval['approval_id']}/decision",
        json={"decision": "APPROVE"},
    )
    assert result.json()["status"] == "APPROVED"
    assert client.get("/api/incidents").json() == []
