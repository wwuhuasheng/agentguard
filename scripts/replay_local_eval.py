"""Replay labeled cases against an isolated local demo API.

This measures local regression behavior, not AgentArts model accuracy.
Each case gets a fresh in-memory app. No network server or real tools are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.server import create_app

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evaluation" / "local_replay_seed.jsonl"
PROVENANCE = {"SYNTHETIC_DEMO", "SYNTHETIC_ATTACK", "REAL_DEIDENTIFIED"}


def revision_info() -> tuple[str, bool]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True, timeout=3,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True, timeout=3,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown", True
    return revision, bool(dirty)


def load_cases(path: Path) -> list[dict]:
    cases = []
    seen = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        case = json.loads(line)
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"line {line_number}: case ID missing or duplicated")
        seen.add(case_id)
        if not isinstance(case.get("category"), str) or not case["category"]:
            raise ValueError(f"{case_id}: category is required")
        if (
            not isinstance(case.get("provenance"), str)
            or case["provenance"] not in PROVENANCE
        ):
            raise ValueError(f"{case_id}: provenance must be explicit")
        if case["provenance"] == "REAL_DEIDENTIFIED":
            evidence_ref = case.get("evidence_ref")
            if not isinstance(evidence_ref, str) or not evidence_ref.strip():
                raise ValueError(f"{case_id}: real case requires evidence_ref")
        if not isinstance(case.get("request"), dict):
            raise ValueError(f"{case_id}: request must be an object")
        decisions = case.get("approval_decisions", [])
        if not isinstance(decisions, list) or any(
            not isinstance(decision, str) or decision not in {"APPROVE", "REJECT"}
            for decision in decisions
        ):
            raise ValueError(f"{case_id}: invalid approval decisions")
        expected = case.get("expected")
        if not isinstance(expected, dict) or not {
            "preview_decisions", "tools", "status", "possible_instruction",
            "side_effects", "initial_status", "approval_tools",
        } <= expected.keys():
            raise ValueError(f"{case_id}: expected fields are incomplete")
        cases.append(case)
    if not cases:
        raise ValueError("evaluation file has no cases")
    return cases


def run_case(case: dict) -> dict:
    app = create_app()
    client = TestClient(app)
    request = case["request"]
    workspace = app.state.runtime.service.workspace
    before = workspace.snapshot()
    result = {
        "id": case["id"], "category": case["category"],
        "provenance": case["provenance"], "passed": False,
    }
    preview = client.post(
        "/api/activities/preview",
        json={key: request[key] for key in ("title", "description", "activity")},
    )
    if preview.status_code != 200:
        return {**result, "error": f"preview HTTP {preview.status_code}"}
    preview_body = preview.json()
    created = client.post("/api/tasks", json=request)
    if created.status_code != 201:
        return {**result, "error": f"create HTTP {created.status_code}"}
    task = created.json()
    initial_status = task["status"]
    approval_tools = []
    for decision in case.get("approval_decisions", []):
        pending = [
            item for item in client.get("/api/approvals").json()
            if item["task_id"] == task["task_id"] and item["status"] == "PENDING"
        ]
        if len(pending) != 1:
            return {**result, "error": "expected exactly one pending approval"}
        approval = pending[0]
        approval_tools.append(approval["tool_request"]["tool_name"])
        response = client.post(
            f"/api/approvals/{approval['approval_id']}/decision",
            json={"decision": decision},
        )
        if response.status_code != 200:
            return {**result, "error": f"approval HTTP {response.status_code}"}
    task = client.get(f"/api/tasks/{task['task_id']}").json()
    after = workspace.snapshot()
    actual = {
        "preview_decisions": [x["decision"] for x in preview_body["steps"]],
        "tools": [x["tool_name"] for x in preview_body["steps"]],
        "initial_status": initial_status,
        "approval_tools": approval_tools,
        "status": task["status"],
        "possible_instruction": next(
            item["evidence"]["reference_signals"].get("possible_instruction", False)
            for item in task["agent_plan"]["agent_evidence"]
            if item["role"] == "CONTENT_ISOLATION_AGENT"
        ),
        "side_effects": {
            "calendar_events": (
                len(after["calendar_events"]) - len(before["calendar_events"])
            ),
            "notifications": (
                len(after["notifications"]) - len(before["notifications"])
            ),
            "files_changed": after["files"] != before["files"],
        },
    }
    expected = case["expected"]
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in actual
        if actual[key] != expected[key]
    }
    return {
        **result, "passed": not mismatches,
        "actual": actual, "mismatches": mismatches,
    }


def replay(path: Path = DEFAULT_CASES) -> dict:
    # Fail before creating the app if a shell environment points at a cloud planner.
    if os.getenv("AGENTGUARD_PLANNER", "local").strip().lower() != "local":
        raise RuntimeError("local replay requires AGENTGUARD_PLANNER=local")
    cases = load_cases(path)
    results = []
    for case in cases:
        try:
            results.append(run_case(case))
        except Exception as exc:
            results.append({
                "id": case["id"], "category": case["category"],
                "provenance": case["provenance"],
                "passed": False, "error": type(exc).__name__,
            })
    by_category = Counter(case["category"] for case in cases)
    passed_by_category = Counter(
        row["category"] for row in results if row["passed"]
    )
    revision, dirty = revision_info()
    provenance_counts = Counter(case["provenance"] for case in cases)
    return {
        "schema_version": 1,
        "source": "LOCAL_REPLAY_NOT_AGENTARTS_EVALUATION",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": revision,
        "working_tree_dirty": dirty,
        "policy_sha256": hashlib.sha256(
            (ROOT / "config" / "policies.json").read_bytes()
        ).hexdigest(),
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "total": len(cases),
        "passed": sum(row["passed"] for row in results),
        "failed": sum(not row["passed"] for row in results),
        "by_provenance": {
            name: provenance_counts[name] for name in sorted(PROVENANCE)
        },
        "by_category": {
            name: {"passed": passed_by_category[name], "total": total}
            for name, total in sorted(by_category.items())
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay(args.cases)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
