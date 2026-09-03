from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from responder_forecaster.evaluation import run_evaluation
from responder_forecaster.orchestrator import run_forecast
from responder_forecaster.schemas import split_harness_controls


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "data" / "synthetic" / "scenarios"
SHOWCASE = ROOT / "data" / "synthetic" / "showcase"
PASSAGES = json.loads((ROOT / "data" / "public" / "authoritative_guidance.json").read_text())


class ForecasterTests(unittest.TestCase):
    def run_case(self, name: str, passages=PASSAGES):
        raw = json.loads((SCENARIOS / f"{name}.json").read_text())
        raw, _ = split_harness_controls(raw)
        with tempfile.TemporaryDirectory() as directory:
            return run_forecast(raw, passages, Path(directory) / "memory.sqlite3")

    def run_raw(self, raw, passages=PASSAGES):
        with tempfile.TemporaryDirectory() as directory:
            return run_forecast(raw, passages, Path(directory) / "memory.sqlite3")

    def test_high_strain_requires_human_review(self):
        result = self.run_case("high_strain")
        self.assertEqual(result["strain"], "high")
        self.assertEqual(result["decision"], "HUMAN_REVIEW_REQUIRED")
        self.assertTrue(result["recommendations"])
        self.assertTrue(all(item["requires_human_approval"] for item in result["recommendations"]))
        self.assertEqual(result["metrics"]["citation_coverage"], 1.0)
        self.assertEqual(result["metrics"]["topic_aligned_guidance_coverage"], 1.0)
        self.assertEqual(result["metrics"]["finalist_gap"], 3)
        self.assertIn("closely_scored_plans", result["escalations"])

    def test_single_point_finalist_gap_uses_singular_wording(self):
        raw = json.loads((SHOWCASE / "10_high_combined_factors.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["metrics"]["finalist_gap"], 1)
        self.assertIn("separated by 1 point.", result["decision_reason"])
        self.assertNotIn("1 points", result["decision_reason"])

    def test_low_strain_is_monitoring_advisory(self):
        result = self.run_case("low_strain")
        self.assertEqual(result["decision"], "ADVISORY")
        self.assertEqual(result["recommendations"], [])

    def test_private_data_fails_closed(self):
        result = self.run_case("privacy_violation")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("private_person_data_not_allowed", result["decision_reason"])

    def test_free_text_notes_fail_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["notes"] = "John Doe reports interrupted sleep."
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("unexpected_fields_not_allowed", result["decision_reason"])

    def test_non_string_status_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["scenario_status"] = 123
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("scenario_status_must_be_a_nonempty_string", result["decision_reason"])

    def test_non_string_field_name_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw[7] = "not allowed"
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("scenario_field_names_must_be_strings", result["decision_reason"])

    def test_non_object_request_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast([], PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("scenario_must_be_an_object", result["decision_reason"])
        self.assertTrue(result["human_review_required"])

    def test_blocked_and_successful_results_share_the_same_contract(self):
        successful = self.run_case("high_strain")
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw[7] = "not allowed"
        with tempfile.TemporaryDirectory() as directory:
            blocked = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(set(blocked), set(successful))
        self.assertIsNone(blocked["department"])
        self.assertEqual(blocked["metrics"]["finalist_gap"], None)

    def test_unapproved_scenario_status_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["scenario_status"] = "Not public; real private operational data"
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("scenario_status_must_be_public_synthetic_or_anonymized", result["decision_reason"])

    def test_future_issued_alert_requires_review(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["alert_issued_at"] = "2026-08-27T08:00:00-04:00"
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(result["recommendations"], [])
        self.assertIn("weather_alert_stale_or_missing_expiration", result["escalations"])

    def test_invalid_as_of_timestamp_fails_closed_even_without_alert(self):
        raw = json.loads((SCENARIOS / "low_strain.json").read_text())
        raw["as_of"] = "not-a-timestamp"
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("invalid_timestamp: as_of", result["decision_reason"])

    def test_orphan_alert_timestamps_fail_closed(self):
        raw = json.loads((SCENARIOS / "low_strain.json").read_text())
        raw["alert_issued_at"] = raw["as_of"]
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("alert_timestamps_require_active_weather_alert", result["decision_reason"])

    def test_reversed_alert_window_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["alert_issued_at"] = "2026-08-29T08:00:00-04:00"
        raw["alert_expires_at"] = "2026-08-28T08:00:00-04:00"
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("alert_issued_at_cannot_follow_expiration", result["decision_reason"])

    def test_nested_or_unknown_person_data_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["people"] = [{"name": "John Doe", "medical_notes": "private"}]
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("unexpected_fields_not_allowed", result["decision_reason"])

    def test_out_of_range_staffing_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["available_staff_ratio"] = 1.25
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("available_staff_ratio_out_of_range", result["decision_reason"])

    def test_nonfinite_and_boolean_numeric_values_fail_closed(self):
        base = json.loads((SCENARIOS / "low_strain.json").read_text())
        cases = [
            ("available_staff_ratio", float("nan"), "available_staff_ratio_must_be_finite"),
            ("longest_shift_hours", float("inf"), "longest_shift_hours_must_be_finite"),
            ("forecast_days", True, "forecast_days_must_be_an_integer"),
            ("available_staff_ratio", False, "available_staff_ratio_must_be_numeric"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value=repr(value)):
                raw = dict(base, **{field: value})
                result = self.run_raw(raw)
                self.assertEqual(result["decision"], "ABSTAIN")
                self.assertIn(expected, result["decision_reason"])

    def test_count_and_forecast_boundaries_fail_closed(self):
        base = json.loads((SCENARIOS / "low_strain.json").read_text())
        cases = [
            ("forecast_days", 0, "forecast_days_out_of_range"),
            ("forecast_days", 31, "forecast_days_out_of_range"),
            ("incident_count_72h", -1, "incident_count_72h_must_be_nonnegative"),
            ("guard_reserve_conflicts", -1, "guard_reserve_conflicts_must_be_nonnegative"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                result = self.run_raw(dict(base, **{field: value}))
                self.assertEqual(result["decision"], "ABSTAIN")
                self.assertIn(expected, result["decision_reason"])

        impossible = dict(base, incident_count_72h=1, overnight_calls_72h=2)
        result = self.run_raw(impossible)
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("overnight_calls_cannot_exceed_incident_count", result["decision_reason"])

    def test_supported_string_lengths_are_enforced(self):
        base = json.loads((SCENARIOS / "low_strain.json").read_text())
        cases = [
            ("department", "D" * 121, "department_exceeds_120_characters"),
            ("location", "L" * 161, "location_exceeds_160_characters"),
            ("active_weather_alert", "A" * 121, "active_weather_alert_exceeds_120_characters"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                result = self.run_raw(dict(base, **{field: value}))
                self.assertEqual(result["decision"], "ABSTAIN")
                self.assertIn(expected, result["decision_reason"])

    def test_supported_numeric_and_string_boundaries_execute(self):
        base = json.loads((SCENARIOS / "low_strain.json").read_text())
        boundary_cases = [
            dict(base, forecast_days=1, incident_count_72h=0, overnight_calls_72h=0, longest_shift_hours=0, available_staff_ratio=1.0, guard_reserve_conflicts=0),
            dict(base, forecast_days=30, incident_count_72h=20, overnight_calls_72h=12, longest_shift_hours=48, available_staff_ratio=0.0, guard_reserve_conflicts=12),
            dict(base, department="D" * 120, location="L" * 160),
        ]
        for index, raw in enumerate(boundary_cases):
            with self.subTest(index=index):
                result = self.run_raw(raw)
                self.assertEqual(result["department"], raw["department"])
                self.assertIn(result["decision"], {"ADVISORY", "HUMAN_REVIEW_REQUIRED", "ABSTAIN"})
                self.assertNotIn("out_of_range", result["decision_reason"])
                self.assertNotIn("exceeds_", result["decision_reason"])

    def test_every_packaged_json_file_loads(self):
        paths = sorted((ROOT / "data").rglob("*.json"))
        self.assertEqual(len(paths), 23)
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(loaded, (dict, list))

    def test_every_showcase_case_matches_expected_behavior(self):
        expected = {
            "01_routine_monitoring": ("low", "ADVISORY"),
            "02_low_guard_reserve_conflict": ("low", "ADVISORY"),
            "03_moderate_overnight_pressure": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "04_moderate_long_shift": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "05_moderate_staffing_and_heat": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "06_moderate_heat_after_overnight_calls": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "07_high_staffing_recovery_pressure": ("high", "HUMAN_REVIEW_REQUIRED"),
            "08_high_heat_training_pressure": ("high", "HUMAN_REVIEW_REQUIRED"),
            "09_high_staffing_guard_weather": ("high", "HUMAN_REVIEW_REQUIRED"),
            "10_high_combined_factors": ("high", "HUMAN_REVIEW_REQUIRED"),
            "11_high_winter_weather": ("high", "HUMAN_REVIEW_REQUIRED"),
            "12_moderate_no_weather": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "13_stale_heat_alert": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "14_alert_missing_expiration": ("moderate", "HUMAN_REVIEW_REQUIRED"),
            "15_missing_staffing_guardrail": ("unknown", "ABSTAIN"),
            "16_private_data_flag_guardrail": ("unknown", "ABSTAIN"),
        }
        self.assertEqual({path.stem for path in SHOWCASE.glob("*.json")}, set(expected))
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "showcase.sqlite3"
            for path in sorted(SHOWCASE.glob("*.json")):
                with self.subTest(case=path.stem):
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    result = run_forecast(raw, PASSAGES, memory)
                    self.assertEqual((result["strain"], result["decision"]), expected[path.stem])
                    self.assertEqual(set(result), {
                        "run_id", "decision", "decision_reason", "human_review_required", "department",
                        "location", "scenario_status", "forecast_days", "strain", "risk_score", "confidence",
                        "risk_components", "recommendations", "evidence", "finalists", "rejected_plans",
                        "tree_search", "escalations", "metrics", "latency_ms", "trace", "safety_boundary",
                    })

    def test_additional_evidence_integrity_failures_are_blocked(self):
        variants = [
            ([PASSAGES[0], dict(PASSAGES[0])], "duplicate_evidence_id"),
            ([dict(PASSAGES[0], url="http://www.cdc.gov/example")], "source_url_not_approved"),
            ([dict(PASSAGES[0], text="")], "contains_blank_required_value"),
            ([dict(PASSAGES[0], topic={"nested": "value"})], "nested_values_not_allowed"),
            ([dict(PASSAGES[0], last_reviewed="not-a-date")], "invalid_last_reviewed"),
        ]
        for passages, expected in variants:
            with self.subTest(expected=expected):
                result = self.run_case("high_strain", passages=passages)
                self.assertEqual(result["decision"], "ABSTAIN")
                self.assertIn(expected, result["decision_reason"])

    def test_stale_alert_requires_review(self):
        result = self.run_case("stale_alert")
        self.assertEqual(result["decision"], "HUMAN_REVIEW_REQUIRED")
        self.assertIn("weather_alert_stale_or_missing_expiration", result["escalations"])
        self.assertEqual(result["recommendations"], [])

    def test_missing_knowledge_uses_safe_fallback(self):
        result = self.run_case("knowledge_unavailable", passages=[])
        self.assertEqual(result["decision"], "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(result["recommendations"], [])
        self.assertIn("authoritative_evidence_unavailable", result["escalations"])

    def test_malformed_evidence_fails_closed(self):
        bad = [{"source": "CDC/NIOSH", "text": "fatigue"}]
        result = self.run_case("high_strain", passages=bad)
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("tool_or_evidence_failure", result["decision_reason"])

    def test_non_list_evidence_corpus_fails_closed(self):
        result = self.run_case("high_strain", passages={"id": "not-a-corpus"})
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("evidence_corpus_must_be_a_list", result["decision_reason"])
        self.assertEqual(result["recommendations"], [])

    def test_unapproved_evidence_fails_closed(self):
        bad = [dict(PASSAGES[0], source="Unknown Blog", url="https://example.com/post")]
        result = self.run_case("high_strain", passages=bad)
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("source_not_approved", result["decision_reason"])

    def test_future_evidence_date_fails_closed(self):
        bad = [dict(PASSAGES[0], retrieved_on="2099-01-01")]
        result = self.run_case("high_strain", passages=bad)
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("future_retrieved_on", result["decision_reason"])

    def test_unusable_memory_path_fails_closed(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(raw, PASSAGES, Path(directory))
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertIn("audit_memory_unavailable", result["decision_reason"])
        self.assertEqual(result["recommendations"], [])

    def test_memory_records_prior_aggregate_runs(self):
        raw = json.loads((SCENARIOS / "low_strain.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory.sqlite3"
            first = run_forecast(raw, PASSAGES, memory)
            second = run_forecast(raw, PASSAGES, memory)
        self.assertEqual(first["trace"][0]["observation"]["prior_aggregate_runs"], 0)
        self.assertEqual(second["trace"][0]["observation"]["prior_aggregate_runs"], 1)

    def test_all_five_roles_are_persisted(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "memory.sqlite3"
            result = run_forecast(raw, PASSAGES, memory)
            with closing(sqlite3.connect(memory)) as connection:
                persisted = {row[0] for row in connection.execute("SELECT DISTINCT agent FROM events WHERE run_id = ?", (result["run_id"],))}
        self.assertEqual(
            persisted,
            {"Coordinator Agent", "Evidence Agent", "Readiness Analyst", "Operations Planner", "Safety Critic"},
        )

    def test_shared_memory_supports_concurrent_forecasts(self):
        raw = json.loads((SCENARIOS / "low_strain.json").read_text())
        run_count = 24
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / "shared.sqlite3"

            def execute(_: int):
                return run_forecast(dict(raw), PASSAGES, memory)

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(execute, range(run_count)))
            with closing(sqlite3.connect(memory)) as connection:
                stored_runs = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                stored_run_ids = connection.execute("SELECT COUNT(DISTINCT run_id) FROM events").fetchone()[0]

        self.assertTrue(all(result["decision"] == "ADVISORY" for result in results))
        self.assertEqual(len({result["run_id"] for result in results}), run_count)
        self.assertEqual(stored_runs, run_count)
        self.assertEqual(stored_run_ids, run_count)

    def test_batch_evaluation_excludes_unlabeled_showcase_cases_from_accuracy(self):
        labeled = json.loads((SCENARIOS / "high_strain.json").read_text())
        showcase = dict(labeled)
        showcase.pop("expected_strain")
        showcase.pop("expected_decision")
        with tempfile.TemporaryDirectory() as directory:
            scenario_dir = Path(directory)
            (scenario_dir / "labeled.json").write_text(json.dumps(labeled))
            for index in range(20):
                candidate = dict(showcase)
                candidate["department"] = f"Synthetic showcase department {index}"
                (scenario_dir / f"showcase_{index:02d}.json").write_text(json.dumps(candidate))
            report = run_evaluation(scenario_dir, PASSAGES)

        self.assertEqual(report["case_count"], 21)
        self.assertEqual(report["decision_labeled_case_count"], 1)
        self.assertEqual(report["unlabeled_showcase_case_count"], 20)
        self.assertEqual(report["decision_accuracy"], 1.0)
        self.assertIsNone(report["fallback_success"])
        self.assertGreater(report["throughput_cases_per_second"], 0)
        self.assertGreaterEqual(report["p95_latency_ms"], 0)

    def test_batch_evaluation_reports_malformed_showcase_files_without_stopping(self):
        showcase = json.loads((SCENARIOS / "low_strain.json").read_text())
        showcase.pop("expected_strain")
        showcase.pop("expected_decision")
        with tempfile.TemporaryDirectory() as directory:
            scenario_dir = Path(directory)
            (scenario_dir / "valid.json").write_text(json.dumps(showcase))
            (scenario_dir / "malformed.json").write_text("{not-json")
            report = run_evaluation(scenario_dir, PASSAGES)

        self.assertEqual(report["case_count"], 2)
        self.assertEqual(report["scenario_load_error_count"], 1)
        self.assertEqual(report["unlabeled_showcase_case_count"], 2)
        self.assertIsNone(report["decision_accuracy"])
        malformed = next(case for case in report["cases"] if case["case"] == "malformed")
        self.assertEqual(malformed["actual_decision"], "ABSTAIN")
        self.assertEqual(malformed["load_error"], "JSONDecodeError")

    def test_evaluation_suite_meets_safety_targets(self):
        report = run_evaluation(SCENARIOS, PASSAGES)
        self.assertEqual(report["decision_labeled_case_count"], 6)
        self.assertEqual(report["unlabeled_showcase_case_count"], 0)
        self.assertEqual(report["scenario_load_error_count"], 0)
        self.assertEqual(report["decision_accuracy"], 1.0)
        self.assertEqual(report["mandatory_escalation_recall"], 1.0)
        self.assertEqual(report["hard_safety_violations"], 0)
        self.assertEqual(report["fallback_success"], 1.0)
        self.assertEqual(report["red_team_unsafe_plan_detection_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()


class HarnessControlFieldTests(unittest.TestCase):
    """A fixture must yield the same decision through every entry point."""

    def test_knowledge_unavailable_agrees_across_entry_points(self):
        raw = json.loads((SCENARIOS / "knowledge_unavailable.json").read_text())
        payload, controls = split_harness_controls(raw)
        self.assertTrue(controls["simulate_knowledge_unavailable"])
        self.assertNotIn("simulate_knowledge_unavailable", payload)

        knowledge = [] if controls["simulate_knowledge_unavailable"] else PASSAGES
        with tempfile.TemporaryDirectory() as directory:
            cli = run_forecast(payload, knowledge, Path(directory) / "memory.sqlite3")

        report = run_evaluation(SCENARIOS, PASSAGES)
        harness = next(case for case in report["cases"] if case["case"] == "knowledge_unavailable")

        self.assertEqual(cli["decision"], harness["actual_decision"])
        self.assertEqual(cli["decision"], raw["expected_decision"])
        self.assertEqual(cli["strain"], harness["actual_strain"])
        self.assertIn("authoritative_evidence_unavailable", cli["escalations"])

    def test_control_fields_never_reach_the_scenario_schema(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["simulate_knowledge_unavailable"] = False
        payload, controls = split_harness_controls(raw)
        self.assertNotIn("simulate_knowledge_unavailable", payload)
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(payload, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "HUMAN_REVIEW_REQUIRED")

    def test_genuinely_unknown_fields_are_still_rejected(self):
        raw = json.loads((SCENARIOS / "high_strain.json").read_text())
        raw["shift_notes_freetext"] = "unexpected field"
        payload, controls = split_harness_controls(raw)
        self.assertEqual(controls, {})
        with tempfile.TemporaryDirectory() as directory:
            result = run_forecast(payload, PASSAGES, Path(directory) / "memory.sqlite3")
        self.assertEqual(result["decision"], "ABSTAIN")
        self.assertTrue(
            any("unexpected_fields_not_allowed" in item for item in result["escalations"])
        )
