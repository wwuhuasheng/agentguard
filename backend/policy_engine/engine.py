from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.models import (
    Decision,
    PolicyDecision,
    RiskEvidence,
    RiskLevel,
    ToolRequest,
    TrustLevel,
)


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class PolicyRepository:
    def __init__(self, policies: List[Dict[str, Any]]) -> None:
        self._policies = policies

    @classmethod
    def from_json(cls, path: Path) -> "PolicyRepository":
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        return cls(document["policies"])

    def find(self, agent_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        candidates = [
            item
            for item in self._policies
            if item["tool"] == tool_name
            and item.get("agent", "*") in {"*", agent_id}
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.get("agent") == agent_id, reverse=True)
        return candidates[0]


class PolicyEngine:
    """Deterministic enforcement. LLMs may add evidence but cannot bypass it."""

    def __init__(self, repository: PolicyRepository) -> None:
        self.repository = repository

    def evaluate(self, request: ToolRequest) -> PolicyDecision:
        policy = self.repository.find(request.agent_id, request.tool_name)
        if policy is None:
            return self._decision(
                request,
                Decision.BLOCK,
                None,
                self._evidence(
                    "POLICY_NOT_FOUND",
                    "该 Agent 没有此工具的授权策略。",
                    RiskLevel.CRITICAL,
                    "tool_name",
                    request.tool_name,
                ),
            )

        if request.action in policy.get("denied_actions", []):
            return self._decision(
                request,
                Decision.BLOCK,
                policy,
                self._evidence(
                    "ACTION_DENIED",
                    "该操作被策略明确禁止。",
                    RiskLevel.CRITICAL,
                    "action",
                    request.action,
                ),
            )

        allowed_actions = policy.get("allowed_actions", [])
        if request.action not in allowed_actions:
            return self._decision(
                request,
                Decision.BLOCK,
                policy,
                self._evidence(
                    "ACTION_NOT_ALLOWED",
                    "该操作不在 Agent 的允许范围内。",
                    RiskLevel.HIGH,
                    "action",
                    request.action,
                    allowed_actions,
                ),
            )

        blockers = self._blocking_checks(request, policy)
        if blockers:
            return self._decision(request, Decision.BLOCK, policy, blockers)

        confirmations = self._confirmation_checks(request, policy)
        if confirmations:
            return self._decision(request, Decision.CONFIRM, policy, confirmations)

        return PolicyDecision(
            request_id=request.request_id,
            decision=Decision.ALLOW,
            risk_level=RiskLevel.LOW,
            reasons=[
                self._evidence(
                    "POLICY_MATCHED",
                    "工具、操作和参数均符合当前授权。",
                    RiskLevel.LOW,
                )
            ],
            policy_id=policy["id"],
        )

    def _blocking_checks(
        self, request: ToolRequest, policy: Dict[str, Any]
    ) -> List[RiskEvidence]:
        evidence: List[RiskEvidence] = []
        arguments = request.arguments

        if (
            request.source_trust == TrustLevel.EXTERNAL_UNTRUSTED
            and request.action in policy.get("external_source_blocked_actions", [])
        ):
            evidence.append(
                self._evidence(
                    "UNTRUSTED_SOURCE_ESCALATION",
                    "外部文档不能触发该高影响操作。",
                    RiskLevel.CRITICAL,
                    "source_trust",
                    request.source_trust.value,
                )
            )

        allowed_domains = policy.get("allowed_recipient_domains", [])
        recipient = arguments.get("recipient")
        if recipient and allowed_domains:
            domain = recipient.rsplit("@", 1)[-1].lower() if "@" in recipient else ""
            if domain not in allowed_domains:
                evidence.append(
                    self._evidence(
                        "RECIPIENT_DOMAIN_DENIED",
                        "目标地址不属于允许的接收域。",
                        RiskLevel.CRITICAL,
                        "recipient",
                        recipient,
                        allowed_domains,
                    )
                )

        allowed_prefixes = policy.get("allowed_path_prefixes", [])
        path_value = arguments.get("path")
        if path_value and allowed_prefixes:
            # Normalise separators so the rule behaves identically on Windows.
            normalized = str(Path(path_value)).replace("\\", "/")
            prefixes = [
                str(Path(prefix)).replace("\\", "/") for prefix in allowed_prefixes
            ]
            if ".." in Path(path_value).parts or not any(
                normalized.startswith(prefix) for prefix in prefixes
            ):
                evidence.append(
                    self._evidence(
                        "PATH_OUT_OF_SCOPE",
                        "文件路径超出 Agent 被授权的目录。",
                        RiskLevel.HIGH,
                        "path",
                        path_value,
                        allowed_prefixes,
                    )
                )

        requested_fields = set(arguments.get("fields", []))
        denied_fields = set(policy.get("denied_fields", []))
        exposed = sorted(requested_fields & denied_fields)
        if exposed:
            evidence.append(
                self._evidence(
                    "SENSITIVE_FIELDS_DENIED",
                    "请求包含当前任务不需要的敏感字段。",
                    RiskLevel.HIGH,
                    "fields",
                    exposed,
                )
            )

        return evidence

    def _confirmation_checks(
        self, request: ToolRequest, policy: Dict[str, Any]
    ) -> List[RiskEvidence]:
        evidence: List[RiskEvidence] = []
        if request.action in policy.get("confirmation_actions", []):
            evidence.append(
                self._evidence(
                    "ACTION_REQUIRES_CONFIRMATION",
                    "该操作影响较大，需要用户确认。",
                    RiskLevel.MEDIUM,
                    "action",
                    request.action,
                )
            )

        recipient_count = int(request.arguments.get("recipient_count", 0))
        limit = policy.get("confirmation_recipient_count")
        if limit is not None and recipient_count > int(limit):
            evidence.append(
                self._evidence(
                    "BULK_ACTION_REQUIRES_CONFIRMATION",
                    "接收人数超过自动执行阈值。",
                    RiskLevel.HIGH,
                    "recipient_count",
                    recipient_count,
                    limit,
                )
            )
        return evidence

    @staticmethod
    def _evidence(
        code: str,
        message: str,
        level: RiskLevel,
        field: Optional[str] = None,
        observed: Optional[Any] = None,
        expected: Optional[Any] = None,
    ) -> RiskEvidence:
        return RiskEvidence(code, message, level, field, observed, expected)

    @staticmethod
    def _decision(
        request: ToolRequest,
        decision: Decision,
        policy: Optional[Dict[str, Any]],
        evidence: Any,
    ) -> PolicyDecision:
        reasons = evidence if isinstance(evidence, list) else [evidence]
        risk_level = max(reasons, key=lambda item: _RISK_ORDER[item.level]).level
        return PolicyDecision(
            request_id=request.request_id,
            decision=decision,
            risk_level=risk_level,
            reasons=reasons,
            policy_id=policy["id"] if policy else None,
        )
