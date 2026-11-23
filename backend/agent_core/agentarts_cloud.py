"""Fail-closed AgentArts workflow planner.

AgentArts supplies analysis evidence; only the user-confirmed ActivitySpec may
produce executable tool arguments. The local policy gateway remains mandatory.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from backend.agent_core.agentarts_adapter import DeterministicAgentArtsAdapter
from backend.agent_core.contracts import (
    ActivitySpec,
    AgentEvidence,
    AgentRole,
    OrchestrationPlan,
    PlanningAdapter,
)

_MAX_RESPONSE_BYTES = 1024 * 1024
_RUNTIME_PATH = re.compile(r"/runtimes/[A-Za-z0-9_-]{1,64}/invocations")
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_REDACTED_RECIPIENT = "withheld@example.org"
_REDACTED_NOTICE = "通知正文仅在本地策略与执行链处理"


class AgentArtsError(RuntimeError):
    """A cloud invocation failed; callers must not silently use a local plan."""


class AgentArtsRuntimeClient:
    def __init__(
        self,
        invocation_url: str,
        api_key: str,
        *,
        invoke_mode: str = "published",
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        parsed = urlparse(invocation_url)
        hostname = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or not hostname.endswith((".huaweicloud.com", ".myhuaweicloud.com"))
            or not _RUNTIME_PATH.fullmatch(parsed.path)
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError("AgentArts URL must be an official HTTPS invocation URL")
        token = api_key.removeprefix("Bearer ").strip()
        if not token:
            raise ValueError("AgentArts API key is required")
        if invoke_mode not in {"debug", "published"}:
            raise ValueError("AgentArts invoke mode must be debug or published")
        self.invocation_url = invocation_url
        self._token = token
        self.invoke_mode = invoke_mode
        self.transport = transport

    def invoke(self, inputs: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Return the terminal workflow event without exposing credentials."""
        if not _SESSION_ID.fullmatch(session_id):
            raise AgentArtsError("AgentArts session ID is invalid")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
            "X-Invoke-Mode": self.invoke_mode,
            "x-hw-agentarts-session-id": session_id,
            "X-Request-Id": session_id,
        }
        try:
            with httpx.Client(timeout=60.0, transport=self.transport) as client:
                with client.stream(
                    "POST",
                    self.invocation_url,
                    headers=headers,
                    json={"inputs": inputs},
                ) as response:
                    if response.status_code != 200:
                        raise AgentArtsError(
                            f"AgentArts invocation failed (HTTP {response.status_code})"
                        )
                    events = self._read_events(response)
        except httpx.HTTPError as exc:
            raise AgentArtsError("AgentArts network request failed") from exc

        if any(item.get("event") in {"error", "exception"} for item in events):
            raise AgentArtsError("AgentArts workflow reported an error")
        finished = next(
            (
                item
                for item in reversed(events)
                if item.get("event") == "workflow_finished"
            ),
            None,
        )
        if finished is None:
            raise AgentArtsError("AgentArts workflow did not finish")
        data = finished.get("data")
        if not isinstance(data, dict):
            raise AgentArtsError("AgentArts workflow result is invalid")
        status = data.get("status", {})
        if (
            not isinstance(status, dict)
            or status.get("code") != 1
            or status.get("desc") != "succeeded"
            or data.get("error_code") not in (None, "")
        ):
            raise AgentArtsError("AgentArts workflow did not succeed")
        return finished

    @staticmethod
    def _read_events(response: httpx.Response) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        size = 0
        for line in response.iter_lines():
            size += len(line.encode("utf-8"))
            if size > _MAX_RESPONSE_BYTES:
                raise AgentArtsError("AgentArts response exceeded size limit")
            if line.startswith("data:"):
                value = line[5:].strip()
            elif line.lstrip().startswith("{"):
                value = line.strip()
            else:
                continue
            if not value or value == "[DONE]":
                continue
            try:
                item = json.loads(value)
            except json.JSONDecodeError as exc:
                raise AgentArtsError("AgentArts returned invalid event JSON") from exc
            if not isinstance(item, dict):
                raise AgentArtsError("AgentArts returned an invalid event")
            events.append(item)
        return events


class AgentArtsWorkflowPlanner:
    provider = "huawei-agentarts-workflow"

    def __init__(self, client: AgentArtsRuntimeClient) -> None:
        self.client = client
        self.local = DeterministicAgentArtsAdapter()

    def plan_activity(self, task_id: str, spec: ActivitySpec) -> OrchestrationPlan:
        reference_signals_json = json.dumps(
            spec.reference_signals or {"present": False},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # The task-workflow template exposes query plus typed fields. Recipient
        # and notice are not referenced by any cloud node, but placeholders keep
        # the current Start schema satisfied without exporting private values.
        # The local, user-confirmed spec remains the only source of tool arguments.
        query = json.dumps(
            {
                "title": spec.title,
                "starts_at": spec.starts_at,
                "location": spec.location,
                "recipient_count": spec.recipient_count,
                "source_trust": spec.source_trust.value,
                "update_shared_file": spec.update_shared_file,
                "reference_signals": json.loads(reference_signals_json),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        finished = self.client.invoke(
            {
                "query": query,
                "title": spec.title,
                "starts_at": spec.starts_at,
                "location": spec.location,
                "recipient": _REDACTED_RECIPIENT,
                "recipient_count": spec.recipient_count,
                "notice_content": _REDACTED_NOTICE,
                "source_trust": spec.source_trust.value,
                "update_shared_file": spec.update_shared_file,
                "reference_signals_json": reference_signals_json,
            },
            session_id=task_id,
        )
        output = finished["data"].get("outputs", {})
        if not isinstance(output, dict):
            raise AgentArtsError("AgentArts workflow output is invalid")
        fields = output.get("user_fields") or {}
        raw = fields.get("agent_evidence_json") if isinstance(fields, dict) else None
        raw = raw or output.get("responseContent")
        local_plan = self.local.plan_activity(task_id, spec)
        signals = spec.reference_signals or {}
        safe_evidence = {
            AgentRole.BUSINESS: {
                "selected_steps": [
                    f"{step.tool_name}.{step.action}" for step in local_plan.steps
                ]
            },
            AgentRole.CONTENT_ISOLATION: {
                "reference_present": signals.get("present") is True,
                "possible_instruction": signals.get("possible_instruction") is True,
                "has_sensitive_columns": signals.get("has_sensitive_columns") is True,
            },
            AgentRole.BEHAVIOR_GUARD: {
                "file_update_selected": spec.update_shared_file,
                "notice_count": spec.recipient_count,
                "decision_owner": "POLICY_GATEWAY",
            },
        }
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
            records = value["agent_evidence"]
            if not isinstance(records, list) or len(records) != 3:
                raise ValueError("three agent evidence records are required")
            evidence = []
            for item in records:
                if not isinstance(item, dict):
                    raise ValueError("agent record must be an object")
                role = AgentRole(item["role"])
                conclusion = item["conclusion"]
                claims = item.get("evidence", {})
                expected = safe_evidence[role]
                if (
                    not isinstance(conclusion, str)
                    or not conclusion.strip()
                    or len(conclusion) > 600
                    or not isinstance(claims, dict)
                    or any(
                        key in claims and claims[key] != expected[key]
                        for key in expected
                    )
                ):
                    raise ValueError("agent evidence is malformed")
                evidence.append(AgentEvidence(role, conclusion, expected))
            if {item.role for item in evidence} != set(AgentRole):
                raise ValueError("agent roles are incomplete")
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentArtsError("AgentArts evidence contract was not met") from exc
        # Cloud output is advisory. It never chooses tools or signs a passport.
        execution_id = finished["data"].get("execution_id")
        if not isinstance(execution_id, str) or not _SESSION_ID.fullmatch(execution_id):
            execution_id = None
        return OrchestrationPlan(
            task_id, local_plan.steps, evidence, self.provider,
            execution_id=execution_id,
        )


def planner_from_env() -> PlanningAdapter:
    mode = os.getenv("AGENTGUARD_PLANNER", "local").strip().lower()
    if mode == "local":
        return DeterministicAgentArtsAdapter()
    if mode != "agentarts":
        raise ValueError("AGENTGUARD_PLANNER must be local or agentarts")
    url = os.getenv("AGENTARTS_INVOCATION_URL", "")
    key = os.getenv("AGENTARTS_API_KEY", "")
    return AgentArtsWorkflowPlanner(
        AgentArtsRuntimeClient(
            url, key, invoke_mode=os.getenv("AGENTARTS_INVOKE_MODE", "published")
        )
    )
