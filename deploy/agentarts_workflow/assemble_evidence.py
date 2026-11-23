"""Copy this main function into an AgentArts workflow code node.

The node is an output adapter, not an authorization or execution gateway.
Map its input/output parameters exactly as documented in
docs/agentarts-workflow-kit.md.
"""


def main(args: dict) -> dict:
    import json

    conclusions = {}
    for key in ("business_conclusion", "isolation_conclusion", "guard_conclusion"):
        value = args.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(key + " must be a non-empty string")
        conclusions[key] = value.strip()[:600]

    update_shared_file = args.get("update_shared_file")
    recipient_count = args.get("recipient_count")
    if not isinstance(update_shared_file, bool):
        raise ValueError("update_shared_file must be boolean")
    if isinstance(recipient_count, bool) or not isinstance(recipient_count, int):
        raise ValueError("recipient_count must be integer")
    if recipient_count < 1:
        raise ValueError("recipient_count must be positive")

    signals = json.loads(args.get("reference_signals_json", "{}"))
    if not isinstance(signals, dict):
        raise ValueError("reference_signals_json must encode an object")
    steps = ["calendar.create"]
    if update_shared_file:
        steps.append("shared_file.update")
    steps.append("send_notice.send")
    records = [
        {
            "role": "BUSINESS_AGENT",
            "conclusion": conclusions["business_conclusion"],
            "evidence": {"selected_steps": steps},
        },
        {
            "role": "CONTENT_ISOLATION_AGENT",
            "conclusion": conclusions["isolation_conclusion"],
            "evidence": {
                "reference_present": signals.get("present") is True,
                "possible_instruction": signals.get("possible_instruction") is True,
                "has_sensitive_columns": signals.get("has_sensitive_columns") is True,
            },
        },
        {
            "role": "BEHAVIOR_GUARD_AGENT",
            "conclusion": conclusions["guard_conclusion"],
            "evidence": {
                "file_update_selected": update_shared_file,
                "notice_count": recipient_count,
                "decision_owner": "POLICY_GATEWAY",
            },
        },
    ]
    return {"agent_evidence_json": json.dumps(
        {"agent_evidence": records}, ensure_ascii=False, separators=(",", ":")
    )}
