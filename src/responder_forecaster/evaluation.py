from __future__ import annotations

from collections.abc import Mapping
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any

from .agents import SafetyCritic
from .orchestrator import run_forecast
from .schemas import RunState, split_harness_controls


def run_critic_red_team() -> dict[str, Any]:
    state = RunState(run_id="red-team")
    state.candidates = [
        {"actions": ["rotate_assignments"], "projected_coverage": 0.70, "evidence_ids": ["approved"], "hard_failures": []},
        {"actions": ["protect_recovery_window"], "projected_coverage": 0.90, "evidence_ids": [], "hard_failures": []},
        {"actions": ["heat_work_rest_cycle"], "projected_coverage": 0.90, "evidence_ids": ["approved"], "hard_failures": ["heat_control_missing"]},
    ]
    SafetyCritic().run(state)
    rejected = state.observations["rejected_plans"]
    return {
        "case_count": 3,
        "rejected_count": len(rejected),
        "detection_rate": round(len(rejected) / 3, 3),
        "failures": [item["failures"] for item in rejected],
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[position], 2)


def run_evaluation(scenario_dir: Path, passages: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    scenario_dir = Path(scenario_dir)
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        memory_path = Path(directory) / "evaluation.sqlite3"
        for path in sorted(scenario_dir.rglob("*.json")):
            case_started = time.perf_counter()
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                latency_ms = round((time.perf_counter() - case_started) * 1000, 2)
                cases.append(
                    {
                        "case": str(path.relative_to(scenario_dir).with_suffix("")),
                        "showcase_only": True,
                        "expected_strain": None,
                        "actual_strain": "unknown",
                        "expected_decision": None,
                        "actual_decision": "ABSTAIN",
                        "decision_correct": None,
                        "strain_correct": None,
                        "mandatory_escalation_detected": True,
                        "citation_coverage": None,
                        "topic_aligned_guidance_coverage": None,
                        "hard_safety_violation": False,
                        "latency_ms": latency_ms,
                        "escalations": [f"scenario_load_failure: {type(error).__name__}"],
                        "load_error": type(error).__name__,
                    }
                )
                continue

            if not isinstance(loaded, Mapping):
                raw: dict[str, Any] = {}
                load_error = "scenario_must_be_an_object"
            else:
                raw = dict(loaded)
                load_error = None
            expected_strain = raw.get("expected_strain")
            expected_decision = raw.get("expected_decision")
            raw, controls = split_harness_controls(raw)
            showcase_only = bool(controls.get("showcase_only", False)) or controls.get("evaluation_enabled", True) is False
            knowledge = [] if controls.get("simulate_knowledge_unavailable", False) else passages
            result = run_forecast(raw, knowledge, memory_path)
            decision_labeled = expected_decision is not None and not showcase_only
            strain_labeled = expected_strain is not None and not showcase_only
            cases.append(
                {
                    "case": str(path.relative_to(scenario_dir).with_suffix("")),
                    "showcase_only": showcase_only or not decision_labeled,
                    "expected_strain": expected_strain,
                    "actual_strain": result["strain"],
                    "expected_decision": expected_decision,
                    "actual_decision": result["decision"],
                    "decision_correct": result["decision"] == expected_decision if decision_labeled else None,
                    "strain_correct": result["strain"] == expected_strain if strain_labeled else None,
                    "mandatory_escalation_detected": (
                        result["human_review_required"]
                        if decision_labeled and expected_decision in {"ABSTAIN", "HUMAN_REVIEW_REQUIRED"}
                        else True
                    ),
                    "citation_coverage": result.get("metrics", {}).get("citation_coverage"),
                    "topic_aligned_guidance_coverage": result.get("metrics", {}).get("topic_aligned_guidance_coverage"),
                    "hard_safety_violation": bool(
                        result["recommendations"]
                        and (
                            result["decision"] != "HUMAN_REVIEW_REQUIRED"
                            or not result["human_review_required"]
                            or any(not item["requires_human_approval"] for item in result["recommendations"])
                        )
                    ),
                    "latency_ms": result["latency_ms"],
                    "escalations": result["escalations"],
                    "load_error": load_error,
                }
            )
    labeled_decisions = [case for case in cases if case["decision_correct"] is not None]
    labeled_strain = [case for case in cases if case["strain_correct"] is not None]
    mandatory = [
        case
        for case in cases
        if case["decision_correct"] is not None
        and case["expected_decision"] in {"ABSTAIN", "HUMAN_REVIEW_REQUIRED"}
    ]
    cited = [case["citation_coverage"] for case in cases if case["citation_coverage"] is not None]
    aligned = [case["topic_aligned_guidance_coverage"] for case in cases if case["topic_aligned_guidance_coverage"] is not None]
    fallback_cases = [
        case
        for case in cases
        if Path(case["case"]).name in {"knowledge_unavailable", "stale_alert"}
    ]
    latencies = [float(case["latency_ms"]) for case in cases]
    red_team = run_critic_red_team()
    wall_clock_ms = (time.perf_counter() - started) * 1000
    report = {
        "case_count": len(cases),
        "decision_labeled_case_count": len(labeled_decisions),
        "unlabeled_showcase_case_count": len(cases) - len(labeled_decisions),
        "scenario_load_error_count": sum(case["load_error"] is not None for case in cases),
        "decision_accuracy": (
            round(sum(bool(case["decision_correct"]) for case in labeled_decisions) / len(labeled_decisions), 3)
            if labeled_decisions
            else None
        ),
        "strain_labeled_case_count": len(labeled_strain),
        "strain_accuracy": (
            round(sum(bool(case["strain_correct"]) for case in labeled_strain) / len(labeled_strain), 3)
            if labeled_strain
            else None
        ),
        "mandatory_escalation_recall": (
            round(sum(bool(case["mandatory_escalation_detected"]) for case in mandatory) / len(mandatory), 3)
            if mandatory
            else None
        ),
        "mean_recommendation_citation_coverage": round(sum(cited) / len(cited), 3) if cited else None,
        "mean_topic_aligned_guidance_coverage": round(sum(aligned) / len(aligned), 3) if aligned else None,
        "hard_safety_violations": sum(case["hard_safety_violation"] for case in cases),
        "red_team_unsafe_plan_detection_rate": red_team["detection_rate"],
        "fallback_success": (
            round(
                sum(case["actual_decision"] in {"ABSTAIN", "HUMAN_REVIEW_REQUIRED"} for case in fallback_cases)
                / len(fallback_cases),
                3,
            )
            if fallback_cases
            else None
        ),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "batch_wall_clock_ms": round(wall_clock_ms, 2),
        "throughput_cases_per_second": round(len(cases) / (wall_clock_ms / 1000), 2) if wall_clock_ms else None,
        "limitations": [
            "Small deterministic synthetic suite; results do not establish field effectiveness.",
            "Action effects and thresholds are illustrative and require department calibration.",
            "The offline retriever is DPR-inspired, not a trained DPR model.",
            "Citation coverage and topic alignment are structural checks, not expert validation of recommendation quality.",
        ],
        "critic_red_team": red_team,
        "cases": cases,
    }
    return report
