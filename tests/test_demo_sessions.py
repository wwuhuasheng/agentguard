from fastapi.testclient import TestClient

from backend.api.demo_sessions import DemoSessionStore
from backend.api.server import TaskServiceRuntime, create_app


def test_visitor_sessions_isolate_tasks_approvals_and_mock_tools():
    app = create_app(isolated_sessions=True)
    first = TestClient(app)
    second = TestClient(app)

    first_user = first.get("/api/me")
    second_user = second.get("/api/me")
    assert first_user.status_code == second_user.status_code == 200
    assert first_user.json()["user_id"] != second_user.json()["user_id"]
    assert "HttpOnly" in first_user.headers["set-cookie"]
    assert "SameSite=lax" in first_user.headers["set-cookie"]

    created = first.post(
        "/api/tasks", json={"title": "访客甲通知", "scenario": "approval"}
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    approval_id = first.get("/api/approvals").json()[0]["approval_id"]
    assert second.get("/api/tasks").json() == []
    assert second.get("/api/approvals").json() == []
    assert second.get("/api/tasks/" + task_id).status_code == 404
    assert second.get("/api/tasks/" + task_id + "/events").status_code == 404
    assert (
        second.post(
            "/api/approvals/" + approval_id + "/decision",
            json={"decision": "APPROVE"},
        ).status_code
        == 404
    )
    assert first.get("/api/approvals").json()[0]["status"] == "PENDING"
    assert first.get("/api/tasks/" + task_id).status_code == 200
    assert first.post(
        "/api/approvals/" + approval_id + "/decision",
        json={"decision": "APPROVE"},
    ).status_code == 200
    assert second.get("/api/tasks").json() == []
    first_runtime = app.state.sessions.get_or_create(
        first.cookies.get("agentguard_demo_session")
    )[1]
    second_runtime = app.state.sessions.get_or_create(
        second.cookies.get("agentguard_demo_session")
    )[1]
    assert len(first_runtime.service.workspace.notifications) == 1
    assert second_runtime.service.workspace.notifications == []
    assert second.get("/core/health").status_code == 404


def test_visitor_mode_rejects_untrusted_post_origin():
    client = TestClient(create_app(isolated_sessions=True))
    client.get("/api/me")
    result = client.post(
        "/api/tasks",
        json={"title": "跨站操作", "scenario": "normal"},
        headers={"Origin": "https://untrusted.example"},
    )
    assert result.status_code == 403
    assert client.get("/api/tasks").json() == []


def test_health_does_not_allocate_visitor_or_consume_capacity():
    app = create_app(isolated_sessions=True)
    app.state.sessions = DemoSessionStore(TaskServiceRuntime, max_sessions=1)
    assert TestClient(app).get("/api/health").status_code == 200
    assert len(app.state.sessions) == 0
    first = TestClient(app)
    second = TestClient(app)
    assert first.get("/api/me").status_code == 200
    assert second.get("/api/me").status_code == 503
    assert first.get("/api/tasks").status_code == 200


def test_idle_session_expires_and_issues_new_runtime():
    now = [100.0]
    store = DemoSessionStore(
        object, idle_seconds=10, max_sessions=1, clock=lambda: now[0]
    )
    session_id, first, created = store.get_or_create(None)
    assert created is True
    now[0] = 111.0
    new_id, second, created = store.get_or_create(session_id)
    assert created is True
    assert new_id != session_id
    assert first is not second
