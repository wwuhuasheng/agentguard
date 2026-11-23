import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.replay_local_eval import DEFAULT_CASES, load_cases, replay


class LocalEvaluationReplayTests(unittest.TestCase):
    def test_approval_and_rejection_replay_preserves_expected_side_effects(self):
        report = replay(DEFAULT_CASES)
        self.assertEqual((report["passed"], report["total"]), (8, 8))
        self.assertEqual(report["by_provenance"]["SYNTHETIC_DEMO"], 8)
        self.assertEqual(report["by_provenance"]["REAL_DEIDENTIFIED"], 0)
        by_id = {row["id"]: row for row in report["results"]}
        self.assertTrue(by_id["LOCAL-06"]["actual"]["side_effects"]["files_changed"])
        self.assertEqual(
            by_id["LOCAL-08"]["actual"]["side_effects"],
            {"calendar_events": 0, "notifications": 0, "files_changed": False},
        )

    def test_incorrect_label_stays_in_denominator_and_reports_mismatch(self):
        case = load_cases(DEFAULT_CASES)[0]
        case["expected"]["status"] = "BLOCKED"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(case, ensure_ascii=False) + "\n", "utf-8")
            report = replay(path)
        self.assertEqual(
            (report["total"], report["passed"], report["failed"]),
            (1, 0, 1),
        )
        self.assertEqual(
            report["results"][0]["mismatches"]["status"]["actual"],
            "COMPLETED",
        )

    def test_cloud_planner_environment_is_rejected_before_replay(self):
        with patch.dict(os.environ, {"AGENTGUARD_PLANNER": "agentarts"}):
            with self.assertRaisesRegex(
                RuntimeError, "requires AGENTGUARD_PLANNER=local"
            ):
                replay(DEFAULT_CASES)

    def test_real_case_requires_evidence_reference_and_is_counted_separately(self):
        demo = load_cases(DEFAULT_CASES)[0]
        real = {**demo, "id": "SOURCE-02", "provenance": "REAL_DEIDENTIFIED"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(json.dumps(real, ensure_ascii=False) + "\n", "utf-8")
            with self.assertRaisesRegex(ValueError, "requires evidence_ref"):
                load_cases(path)
            real["evidence_ref"] = "private-organizer-record-001"
            path.write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False) for row in (demo, real)
                ) + "\n",
                "utf-8",
            )
            report = replay(path)
        self.assertEqual(report["by_provenance"]["SYNTHETIC_DEMO"], 1)
        self.assertEqual(report["by_provenance"]["REAL_DEIDENTIFIED"], 1)
        self.assertNotIn("evidence_ref", report["results"][1])


if __name__ == "__main__":
    unittest.main()
