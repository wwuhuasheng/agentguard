"""Versioned, read-only explanations for deterministic policy reason codes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parents[1]
_GUIDANCE = _ROOT / "config" / "policy_guidance.json"
_POLICIES = _ROOT / "config" / "policies.json"


def explain_policy(reason_code: str) -> Dict[str, Any]:
    """Return curated guidance, never a policy change or execution grant."""
    guidance_bytes = _GUIDANCE.read_bytes()
    document = json.loads(guidance_bytes)
    entry = document["entries"].get(reason_code)
    if entry is None:
        raise ValueError("unknown policy reason code")
    return {
        "mode": "READ_ONLY_GUIDANCE",
        "reason_code": reason_code,
        "meaning": entry["meaning"],
        "next_step": entry["next_step"],
        "rule_ref": entry["rule_ref"],
        "guidance_version": document["version"],
        "guidance_sha256": hashlib.sha256(guidance_bytes).hexdigest(),
        "policy_sha256": hashlib.sha256(_POLICIES.read_bytes()).hexdigest(),
        "warning": "规则解释仅供核对；实际授权仍由策略引擎和任务护照决定。",
    }
