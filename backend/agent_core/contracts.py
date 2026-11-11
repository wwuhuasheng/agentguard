from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from backend.models import ToolRequest, TrustLevel


class AgentRole(str, Enum):
    BUSINESS = "BUSINESS_AGENT"
    CONTENT_ISOLATION = "CONTENT_ISOLATION_AGENT"
    BEHAVIOR_GUARD = "BEHAVIOR_GUARD_AGENT"


@dataclass(frozen=True)
class ActivitySpec:
    title: str
    starts_at: str
    location: str
    recipient: str
    recipient_count: int
    notice_content: str
    source_trust: TrustLevel = TrustLevel.USER_CONFIRMED
    update_shared_file: bool = True
    reference_signals: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class AgentEvidence:
    role: AgentRole
    conclusion: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["role"] = self.role.value
        return value


@dataclass(frozen=True)
class OrchestrationPlan:
    task_id: str
    steps: List[ToolRequest]
    evidence: List[AgentEvidence]
    provider: str

    def summary(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "step_count": len(self.steps),
            "steps": [
                {
                    "agent_id": step.agent_id,
                    "tool_name": step.tool_name,
                    "action": step.action,
                }
                for step in self.steps
            ],
            "agent_evidence": [item.to_dict() for item in self.evidence],
        }


class PlanningAdapter(Protocol):
    """Stable boundary implemented by the local demo and Huawei AgentArts."""

    def plan_activity(self, task_id: str, spec: ActivitySpec) -> OrchestrationPlan: ...
