import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.agent_core import ActivitySpec
from backend.agent_core.agentarts_cloud import (
    AgentArtsError,
    AgentArtsRuntimeClient,
    AgentArtsWorkflowPlanner,
    planner_from_env,
)
from backend.api.server import create_app
from deploy.agentarts_workflow.assemble_evidence import main as assemble_evidence

URL = "https://example.agentarts.cn-southwest-2.myhuaweicloud.com/runtimes/agent-arts-test/invocations"


def future_start():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


EVIDENCE = {
    "agent_evidence": [
        {
            "role": "BUSINESS_AGENT",
            "conclusion": "活动目标已拆解。",
            "evidence": {"source": "agentarts"},
        },
        {
            "role": "CONTENT_ISOLATION_AGENT",
            "conclusion": "外部内容不继承授权。",
            "evidence": {},
        },
        {
            "role": "BEHAVIOR_GUARD_AGENT",
            "conclusion": "高影响操作需要网关裁决。",
            "evidence": {},
        },
    ]
}


def finished_event(output=EVIDENCE):
    return {
        "event": "workflow_finished",
        "data": {
            "status": {"code": 1, "desc": "succeeded"},
            "outputs": {"user_fields": {"agent_evidence_json": json.dumps(output)}},
            "execution_id": "exec-123",
        },
    }


class AgentArtsCloudTests(unittest.TestCase):
    def test_deployed_code_node_contract_round_trips_into_backend(self):
        """The exact code copied to AgentArts must satisfy the runtime bridge."""
        node_output = assemble_evidence(
            {
                "business_conclusion": "按确认参数规划活动。",
                "isolation_conclusion": "外部表格含可疑指令，不继承权限。",
                "guard_conclusion": "共享文件与群发通知须经策略网关确认。",
                "update_shared_file": True,
                "recipient_count": 40,
                "reference_signals_json": json.dumps(
                    {"present": True, "possible_instruction": True,
                     "has_sensitive_columns": True}
                ),
            }
        )
        terminal = finished_event()
        terminal["data"]["outputs"]["user_fields"] = node_output
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, text="data: " + json.dumps(terminal))
        )
        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(URL, "secret", transport=transport)
        )
        spec = ActivitySpec(
            title="读书会", starts_at=future_start(), location="社区图书馆",
            recipient="readers@example.org", recipient_count=40,
            notice_content="提前到场", update_shared_file=True,
            reference_signals={
                "present": True, "possible_instruction": True,
                "has_sensitive_columns": True,
            },
        )
        plan = planner.plan_activity("task-123", spec)
        self.assertEqual(len(plan.evidence), 3)
        self.assertEqual(plan.evidence[1].evidence["possible_instruction"], True)
        self.assertEqual(plan.evidence[2].evidence["decision_owner"], "POLICY_GATEWAY")
        self.assertEqual(plan.steps[2].arguments["recipient"], "readers@example.org")

    def test_invocation_uses_official_contract_and_parses_sse(self):
        calls = []

        def handler(request):
            calls.append(request)
            body = 'data: {"event":"workflow_started"}\n\n'
            body += "data: " + json.dumps(finished_event()) + "\n\n"
            body += 'data: {"event":"end"}\n\n'
            return httpx.Response(
                200, text=body, headers={"content-type": "text/event-stream"}
            )

        client = AgentArtsRuntimeClient(
            URL, "secret-test-key", transport=httpx.MockTransport(handler)
        )
        result = client.invoke({"title": "读书会"}, session_id="task-123")
        self.assertEqual(result["data"]["execution_id"], "exec-123")
        request = calls[0]
        self.assertEqual(request.headers["authorization"], "Bearer secret-test-key")
        self.assertEqual(request.headers["x-hw-agentarts-session-id"], "task-123")
        self.assertEqual(request.headers["x-invoke-mode"], "published")
        self.assertEqual(json.loads(request.content), {"inputs": {"title": "读书会"}})

    def test_cloud_evidence_cannot_change_executable_arguments(self):
        cloud = json.loads(json.dumps(EVIDENCE))
        cloud["steps"] = [
            {"tool_name": "send_notice", "arguments": {"recipient": "attacker.invalid"}}
        ]
        cloud["agent_evidence"][0]["evidence"]["recipient"] = "attacker.invalid"
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200, text="data: " + json.dumps(finished_event(cloud))
            )
        )
        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(URL, "secret", transport=transport)
        )
        spec = ActivitySpec(
            title="读书会",
            starts_at=future_start(),
            location="社区图书馆",
            recipient="readers@example.org",
            recipient_count=12,
            notice_content="提前到场",
        )
        plan = planner.plan_activity("task-123", spec)
        self.assertEqual(plan.provider, "huawei-agentarts-workflow")
        self.assertEqual(plan.steps[2].arguments["recipient"], "readers@example.org")
        self.assertEqual(len(plan.evidence), 3)
        self.assertNotIn("recipient", plan.evidence[0].evidence)

    def test_cloud_cannot_forge_locally_derived_evidence(self):
        cloud = json.loads(json.dumps(EVIDENCE))
        cloud["agent_evidence"][2]["evidence"]["notice_count"] = 999
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200, text="data: " + json.dumps(finished_event(cloud))
            )
        )
        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(URL, "secret", transport=transport)
        )
        spec = ActivitySpec(
            "读书会", future_start(), "社区图书馆", "r@example.org", 12, "通知"
        )
        with self.assertRaisesRegex(AgentArtsError, "evidence contract"):
            planner.plan_activity("task-123", spec)

    def test_malformed_cloud_record_fails_as_upstream_error(self):
        cloud = {"agent_evidence": [None, None, None]}
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200, text="data: " + json.dumps(finished_event(cloud))
            )
        )
        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(URL, "secret", transport=transport)
        )
        spec = ActivitySpec(
            "读书会", future_start(), "社区图书馆", "r@example.org", 12, "通知"
        )
        with self.assertRaisesRegex(AgentArtsError, "evidence contract"):
            planner.plan_activity("task-123", spec)

    def test_cloud_receives_file_choice_but_cannot_add_omitted_file_step(self):
        calls = []

        def handler(request):
            calls.append(json.loads(request.content)["inputs"])
            return httpx.Response(
                200, text="data: " + json.dumps(finished_event(EVIDENCE))
            )

        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(
                URL, "secret", transport=httpx.MockTransport(handler)
            )
        )
        spec = ActivitySpec(
            title="读书会",
            starts_at=future_start(),
            location="社区图书馆",
            recipient="private-reader@example.org",
            recipient_count=12,
            notice_content="私密通知内容仅本地处理",
            update_shared_file=False,
        )
        plan = planner.plan_activity("task-123", spec)
        self.assertIs(calls[0]["update_shared_file"], False)
        self.assertEqual(calls[0]["recipient"], "withheld@example.org")
        self.assertNotIn("private-reader@example.org", str(calls[0]))
        self.assertNotIn("私密通知内容仅本地处理", str(calls[0]))
        self.assertEqual(
            plan.steps[-1].arguments["recipient"], "private-reader@example.org"
        )
        self.assertEqual(
            [step.tool_name for step in plan.steps], ["calendar", "send_notice"]
        )

    def test_fails_closed_on_error_or_invalid_evidence(self):
        error_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, text='data: {"event":"error"}\n')
        )
        client = AgentArtsRuntimeClient(URL, "secret", transport=error_transport)
        with self.assertRaises(AgentArtsError):
            client.invoke({}, "task-123")

        invalid_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200, text="data: " + json.dumps(finished_event({"agent_evidence": []}))
            )
        )
        planner = AgentArtsWorkflowPlanner(
            AgentArtsRuntimeClient(URL, "secret", transport=invalid_transport)
        )
        with self.assertRaises(AgentArtsError):
            planner.plan_activity("task-123", ActivitySpec("x", "t", "l", "r", 1, "n"))

    def test_rejects_invalid_session_and_conflicting_terminal_status(self):
        calls = []

        def handler(request):
            calls.append(request)
            contradictory = finished_event()
            contradictory["data"]["status"]["code"] = 2
            return httpx.Response(200, text="data: " + json.dumps(contradictory))

        client = AgentArtsRuntimeClient(
            URL, "secret", transport=httpx.MockTransport(handler)
        )
        with self.assertRaisesRegex(AgentArtsError, "session ID"):
            client.invoke({}, "contains space")
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(AgentArtsError, "did not succeed"):
            client.invoke({}, "task-123")


    def test_configuration_requires_explicit_mode_and_official_url(self):
        with patch.dict(os.environ, {"AGENTGUARD_PLANNER": "agentarts"}, clear=True):
            with self.assertRaises(ValueError):
                planner_from_env()
        with self.assertRaises(ValueError):
            AgentArtsRuntimeClient(
                "https://attacker.example/runtimes/agent-arts-test/invocations",
                "secret",
            )

    def test_cloud_mode_is_visible_in_existing_console_contract(self):
        private_reference = "role,phone,name\n志愿者,13800000000,用户A\n"
        with patch.dict(
            os.environ,
            {
                "AGENTGUARD_PLANNER": "agentarts",
                "AGENTARTS_INVOCATION_URL": URL,
                "AGENTARTS_API_KEY": "secret",
            },
        ):
            with patch.object(
                AgentArtsRuntimeClient, "invoke", return_value=finished_event()
            ) as invoke:
                client = TestClient(create_app())
                result = client.post(
                    "/api/tasks",
                    json={
                        "title": "读书会",
                        "description": "提前到场",
                        "scenario": "activity",
                        "activity": {
                            "starts_at": future_start(),
                            "location": "社区图书馆",
                            "recipient": "readers@example.org",
                            "recipient_count": 12,
                        },
                        "reference": {
                            "name": "报名表.csv",
                            "content": private_reference,
                        },
                    },
                )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(
            result.json()["agent_plan"]["provider"], "huawei-agentarts-workflow"
        )
        self.assertEqual(result.json()["agent_plan"]["execution_id"], "exec-123")
        inputs = invoke.call_args.args[0]
        query = json.loads(inputs["query"])
        self.assertEqual(query["recipient_count"], 12)
        self.assertEqual(query["reference_signals"]["has_sensitive_columns"], True)
        self.assertNotIn("recipient", query)
        self.assertNotIn("notice_content", query)
        self.assertEqual(
            json.loads(inputs["reference_signals_json"]),
            {
                "present": True,
                "format": "csv",
                "row_count": 1,
                "has_sensitive_columns": True,
                "possible_instruction": False,
            },
        )
        self.assertNotIn("13800000000", str(inputs))
        self.assertNotIn("用户A", str(inputs))
        self.assertNotIn("报名表.csv", str(inputs))
        self.assertNotIn("readers@example.org", str(inputs))
        self.assertNotIn("提前到场", str(inputs))

    def test_cloud_failure_returns_502_without_local_execution(self):
        with patch.dict(
            os.environ,
            {
                "AGENTGUARD_PLANNER": "agentarts",
                "AGENTARTS_INVOCATION_URL": URL,
                "AGENTARTS_API_KEY": "secret",
            },
        ):
            with patch.object(
                AgentArtsRuntimeClient,
                "invoke",
                side_effect=AgentArtsError("AgentArts workflow reported an error"),
            ):
                app = create_app()
                result = TestClient(app).post(
                    "/api/tasks",
                    json={
                        "title": "读书会",
                        "description": "提前到场",
                        "scenario": "activity",
                        "activity": {
                            "starts_at": future_start(),
                            "location": "社区图书馆",
                            "recipient": "readers@example.org",
                            "recipient_count": 12,
                        },
                    },
                )
        self.assertEqual(result.status_code, 502)
        self.assertEqual(app.state.runtime.service.workspace.notifications, [])
        self.assertEqual(app.state.runtime.service.workspace.calendar_events, [])


if __name__ == "__main__":
    unittest.main()
