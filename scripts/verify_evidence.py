"""Check a redacted AgentGuard evidence JSON file and optional saved root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.evidence import verify_evidence_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="exported evidence JSON")
    parser.add_argument(
        "--expect-root", help="event root SHA-256 saved separately at export time"
    )
    args = parser.parse_args()
    try:
        bundle = json.loads(args.file.read_text(encoding="utf-8"))
        result = verify_evidence_bundle(bundle)
        manifest = bundle.get("manifest", {})
        root = manifest.get("event_root_sha256")
        if args.expect_root and args.expect_root != root:
            result["ok"] = False
            result["findings"].append("EXTERNAL_ROOT_MISMATCH")
        print(
            json.dumps(
                {
                    "ok": result["ok"],
                    "task_id": manifest.get("task_id"),
                    "event_count": manifest.get("event_count"),
                    "event_root_sha256": root,
                    "findings": result["findings"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result["ok"] else 1
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print("invalid evidence file: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
