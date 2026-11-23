"""Validate and export fictional workflow evaluation seeds for AgentArts.

This prepares data only. It neither invokes cloud services nor claims scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation" / "agentarts_seed_cases.json"
FIELDS = {
    "query",
    "title",
    "starts_at",
    "location",
    "recipient",
    "recipient_count",
    "notice_content",
    "source_trust",
    "update_shared_file",
    "reference_signals_json",
    "reference_output",
}


def export_cases(source: Path = SOURCE) -> list[dict]:
    cases = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("seed cases must be a non-empty list")
    ids: set[str] = set()
    output = []
    for case in cases:
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("case IDs must be unique non-empty strings")
        ids.add(case_id)
        if not isinstance(case.get("update_shared_file"), bool):
            raise ValueError(f"{case_id}: update_shared_file must be boolean")
        count = case.get("recipient_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(f"{case_id}: recipient_count must be positive integer")
        signals = case.get("reference_signals")
        if not isinstance(signals, dict) or not isinstance(
            signals.get("present"), bool
        ):
            raise ValueError(f"{case_id}: reference_signals must define present")
        for key in ("title", "starts_at", "location", "reference_output"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError(f"{case_id}: {key} must be a non-empty string")
        query = {
            "title": case["title"],
            "starts_at": case["starts_at"],
            "location": case["location"],
            "recipient_count": count,
            "source_trust": "USER_CONFIRMED",
            "update_shared_file": case["update_shared_file"],
            "reference_signals": signals,
        }
        row = {
            "query": json.dumps(query, ensure_ascii=False, separators=(",", ":")),
            "title": case["title"],
            "starts_at": case["starts_at"],
            "location": case["location"],
            "recipient": "withheld@example.org",
            "recipient_count": count,
            "notice_content": "通知正文仅在本地策略与执行链处理",
            "source_trust": "USER_CONFIRMED",
            "update_shared_file": case["update_shared_file"],
            "reference_signals_json": json.dumps(
                signals, ensure_ascii=False, separators=(",", ":")
            ),
            "reference_output": case["reference_output"],
        }
        if set(row) != FIELDS:
            raise ValueError(f"{case_id}: workflow schema mismatch")
        output.append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = export_cases()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"Exported {len(rows)} fictional cases to {args.output}")


if __name__ == "__main__":
    main()
