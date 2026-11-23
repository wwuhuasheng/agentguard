"""Shareable, redacted task evidence with offline integrity and flow checks.

The hash chain detects edits relative to a separately recorded root. It does
not authenticate the server or prove that the original runtime was honest.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping

FORMAT = "agentguard-evidence-v1"
GENESIS = "0" * 64


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _facts(event: Mapping[str, Any]) -> Dict[str, Any]:
    payload = event.get("payload", {})
    kind = event["event_type"]
    if kind == "POLICY_DECISION":
        return {
            "decision": payload.get("decision"),
            "risk_level": payload.get("risk_level"),
            "policy_id": payload.get("policy_id"),
            "reason_codes": [
                reason.get("code") for reason in payload.get("reasons", [])
            ],
        }
    if kind == "APPROVAL_REQUIRED":
        return {
            "request_fingerprint": payload.get("request_fingerprint"),
            "expires_at": payload.get("expires_at"),
        }
    if kind == "APPROVAL_RESOLVED":
        return {
            "approved": payload.get("approved"),
            "request_fingerprint": payload.get("request_fingerprint"),
        }
    if kind == "TOOL_EXECUTED":
        request = payload.get("tool_request") or {}
        return {"tool_name": request.get("tool_name"), "action": request.get("action")}
    if kind == "SOURCE_INSPECTED":
        return {
            "format": payload.get("format"),
            "source_sha256": payload.get("sha256"),
            "flags": payload.get("flags", []),
            "row_count": payload.get("row_count"),
        }
    if kind == "SCHEDULE_ADOPTED":
        return {"assigned_count": payload.get("assigned_count")}
    if kind == "APPROVED_RETRY":
        return {"remaining": payload.get("remaining")}
    return {}


def _event_chain(events: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    previous = GENESIS
    sealed = []
    for sequence, event in enumerate(events, start=1):
        item = {
            "sequence": sequence,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "request_id": event["request_id"],
            "task_id": event["task_id"],
            "created_at": event["created_at"],
            "facts": _facts(event),
            "previous_sha256": previous,
        }
        item["sha256"] = _sha256(item)
        previous = item["sha256"]
        sealed.append(item)
    return sealed


def make_evidence_bundle(
    task: Mapping[str, Any], policy_sha256: str
) -> Dict[str, Any]:
    """Project raw task state into a package without tool arguments or outputs."""
    events = _event_chain(task["events"])
    plan = task.get("agent_plan") or {}
    manifest = {
        "format": FORMAT,
        "scope": "LOCAL_MOCK_TOOLS",
        "task_id": task["task_id"],
        "scenario": task["scenario"],
        "status": task["status"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "planner_provider": plan.get("provider", "none"),
        "policy_sha256": policy_sha256,
        "event_count": len(events),
        "event_root_sha256": events[-1]["sha256"] if events else GENESIS,
    }
    bundle = {
        "manifest": manifest,
        "manifest_sha256": _sha256(manifest),
        "events": events,
        "verification_note": (
            "哈希链可与另行保存的根摘要比对；它不是服务器签名，"
            "不能单独证明原始运行环境或真实业务结果。"
        ),
    }
    bundle["verification"] = verify_evidence_bundle(bundle)
    return bundle


def verify_evidence_bundle(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify internal hashes and authorization-to-execution ordering."""
    if not isinstance(bundle, dict):
        return {"ok": False, "findings": ["INVALID_STRUCTURE"]}
    findings = []
    manifest = bundle.get("manifest")
    events = bundle.get("events")
    if not isinstance(manifest, dict) or not isinstance(events, list):
        return {"ok": False, "findings": ["INVALID_STRUCTURE"]}
    if manifest.get("format") != FORMAT:
        findings.append("INVALID_FORMAT")
    if _sha256(manifest) != bundle.get("manifest_sha256"):
        findings.append("MANIFEST_HASH_MISMATCH")
    if manifest.get("event_count") != len(events):
        findings.append("EVENT_COUNT_MISMATCH")

    previous = GENESIS
    event_ids = set()
    requests: Dict[str, Dict[str, Any]] = {}
    for sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            findings.append("INVALID_EVENT_STRUCTURE")
            continue
        expected_hash = _sha256({k: v for k, v in event.items() if k != "sha256"})
        if (
            event.get("sequence") != sequence
            or event.get("previous_sha256") != previous
            or event.get("sha256") != expected_hash
        ):
            findings.append("EVENT_CHAIN_MISMATCH")
        previous = event.get("sha256", "")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            findings.append("DUPLICATE_EVENT_ID")
        else:
            event_ids.add(event_id)
        if event.get("task_id") != manifest.get("task_id"):
            findings.append("CROSS_TASK_EVENT")
        request_id = event.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            continue
        state = requests.setdefault(
            request_id,
            {
                "decision": None,
                "required_fingerprint": None,
                "resolved": False,
                "approved": False,
                "executed": 0,
            },
        )
        facts = event.get("facts") or {}
        if not isinstance(facts, dict):
            findings.append("INVALID_EVENT_FACTS")
            continue
        kind = event.get("event_type")
        if kind == "POLICY_DECISION":
            decision = facts.get("decision")
            if state["decision"] is not None or not isinstance(
                decision, str
            ) or decision not in {"ALLOW", "CONFIRM", "BLOCK"}:
                findings.append("INVALID_POLICY_DECISION")
            state["decision"] = decision if isinstance(decision, str) else None
        elif kind == "APPROVAL_REQUIRED":
            fingerprint = facts.get("request_fingerprint")
            if (
                state["decision"] != "CONFIRM"
                or not isinstance(fingerprint, str)
                or not fingerprint
                or state["required_fingerprint"] is not None
            ):
                findings.append("APPROVAL_WITHOUT_CONFIRM_DECISION")
            state["required_fingerprint"] = fingerprint
        elif kind == "APPROVAL_RESOLVED":
            if (
                not state["required_fingerprint"]
                or facts.get("request_fingerprint") != state["required_fingerprint"]
                or not isinstance(facts.get("approved"), bool)
                or state["resolved"]
            ):
                findings.append("INVALID_APPROVAL_RESOLUTION")
            state["resolved"] = True
            state["approved"] = facts.get("approved") is True
        elif kind == "TOOL_EXECUTED":
            state["executed"] += 1
            if (
                state["decision"] not in {"ALLOW", "CONFIRM"}
                or (state["decision"] == "CONFIRM" and not state["approved"])
                or state["executed"] > 1
                or not isinstance(facts.get("tool_name"), str)
                or not isinstance(facts.get("action"), str)
            ):
                findings.append("EXECUTION_WITHOUT_AUTHORIZATION")

    if manifest.get("event_root_sha256") != previous:
        findings.append("EVENT_ROOT_MISMATCH")
    return {"ok": not findings, "findings": sorted(set(findings))}
