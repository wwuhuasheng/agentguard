"""Read-only, task-specific permission preview for people and AgentArts MCP."""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from backend.agent_core.agentarts_adapter import DeterministicAgentArtsAdapter
from backend.agent_core.contracts import ActivitySpec
from backend.policy_engine import PassportIssuer, PolicyEngine, PolicyRepository


def preview_activity_permissions(
    repository: PolicyRepository, spec: ActivitySpec
) -> Dict[str, Any]:
    """Run the real rules in isolated state; never grant live execution rights."""
    fields = (
        spec.title,
        spec.starts_at,
        spec.location,
        spec.recipient,
        spec.notice_content,
    )
    if not all(value.strip() for value in fields):
        raise ValueError("activity preview fields must not be empty")
    if spec.recipient_count < 1:
        raise ValueError("recipient_count must be positive")

    preview_engine = PolicyEngine(repository)
    task_id = str(uuid4())
    plan = DeterministicAgentArtsAdapter().plan_activity(task_id, spec)
    _, bound = PassportIssuer(preview_engine.passports).issue(task_id, plan.steps)
    decisions = [preview_engine.evaluate(request) for request in bound]
    descriptions = {
        "calendar": "创建活动日程",
        "shared_file": "更新共享活动文件",
        "send_notice": "发送活动通知",
    }
    scopes = {
        "calendar": f"{spec.starts_at} · {spec.location}",
        "shared_file": "/workspace/activities/plan.md（仅模拟文件）",
        "send_notice": f"{spec.recipient_count} 人 · {spec.recipient}",
    }
    return {
        "mode": "PREVIEW_ONLY",
        "source_trust_assumption": spec.source_trust.value,
        "warning": (
            "仅按当前参数预估；不授权、不审批、不执行工具。"
            "最终以任务提交时的策略结果为准。"
        ),
        "steps": [
            {
                "tool_name": request.tool_name,
                "action": request.action,
                "description": descriptions[request.tool_name],
                "scope": scopes[request.tool_name],
                "decision": decision.decision.value,
                "risk_level": decision.risk_level.value,
                "reasons": [reason.code for reason in decision.reasons],
                "reason_messages": [reason.message for reason in decision.reasons],
            }
            for request, decision in zip(bound, decisions)
        ],
    }
