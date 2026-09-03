from __future__ import annotations

from collections.abc import Mapping
import time
import uuid
from pathlib import Path
from typing import Any

from .agents import EvidenceAgent, OperationsPlanner, ReadinessAnalyst, SafetyCritic, summarize_actions
from .memory import AuditMemory
from .retrieval import EvidenceViolation
from .schemas import Decision, ForecastResult, InputViolation, RunState, Scenario


def _blocked_result(
    run_id: str,
    reason: str,
    latency_ms: float,
    *,
    scenario: Scenario | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> ForecastResult:
    return {
        "run_id": run_id,
        "decision": "ABSTAIN",
        "decision_reason": reason,
        "human_review_required": True,
        "strain": "unknown",
        "risk_score": 0,
        "confidence": 0.0,
        "recommendations": [],
        "evidence": [],
        "finalists": [],
        "department": scenario.department if scenario else None,
        "location": scenario.location if scenario else None,
        "scenario_status": scenario.scenario_status if scenario else None,
        "forecast_days": scenario.forecast_days if scenario else None,
        "risk_components": {},
        "rejected_plans": [],
        "tree_search": None,
        "escalations": [reason],
        "metrics": {
            "citation_coverage": None,
            "topic_aligned_guidance_coverage": None,
            "finalist_gap": None,
        },
        "latency_ms": round(latency_ms, 2),
        "trace": trace or [],
        "safety_boundary": "No individual diagnosis, fitness-for-duty judgment, dispatch action, or schedule change.",
    }


def run_forecast(
    raw_scenario: Mapping[str, Any],
    passages: Any,
    memory_path: Path | str,
) -> ForecastResult:
    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    try:
        scenario = Scenario.from_dict(raw_scenario)
    except InputViolation as error:
        return _blocked_result(run_id, str(error), (time.perf_counter() - started) * 1000)
    except Exception as error:
        reason = f"input_validation_failure: {type(error).__name__}"
        return _blocked_result(run_id, reason, (time.perf_counter() - started) * 1000)

    state = RunState(run_id=run_id, scenario=scenario)
    try:
        memory = AuditMemory(memory_path)
    except Exception as error:
        reason = f"audit_memory_unavailable: {type(error).__name__}"
        return _blocked_result(
            run_id,
            reason,
            (time.perf_counter() - started) * 1000,
            scenario=scenario,
        )

    try:
        prior_runs = memory.prior_run_count()
        state.observe("Coordinator Agent", "understand_case", {"forecast_days": scenario.forecast_days, "prior_aggregate_runs": prior_runs})
        memory.log(run_id, "Coordinator Agent", state.trace[-1]["action"], state.trace[-1]["observation"])

        agents = [EvidenceAgent(), ReadinessAnalyst(), OperationsPlanner(), SafetyCritic()]
        for agent in agents:
            if isinstance(agent, EvidenceAgent):
                agent.run(state, passages)
            else:
                agent.run(state)
            memory.log(run_id, agent.name, state.trace[-1]["action"], state.trace[-1]["observation"])

        assessment = state.observations["readiness"]
        candidate = state.candidates[0] if state.candidates else None
        finalist_gap = None
        if len(state.candidates) >= 2:
            finalist_gap = state.candidates[0]["score"] - state.candidates[1]["score"]

        decision: Decision
        if "authoritative_evidence_unavailable" in state.escalations:
            decision = "HUMAN_REVIEW_REQUIRED"
            reason = "No approved evidence was available; the agent did not create an unsupported plan."
            candidate = None
        elif "weather_alert_stale_or_missing_expiration" in state.escalations:
            decision = "HUMAN_REVIEW_REQUIRED"
            reason = "The weather alert could not be confirmed as current."
            candidate = None
        elif assessment["strain"] == "low":
            decision = "ADVISORY"
            reason = "The synthetic case is low strain; continue monitoring without an operational change."
        elif not candidate:
            decision = "ABSTAIN"
            reason = "No candidate passed the safety critic."
            state.escalations.append("no_safe_candidate")
        else:
            decision = "HUMAN_REVIEW_REQUIRED"
            reasons = ["Every proposed operational change requires authorized approval."]
            if finalist_gap is not None and finalist_gap <= 3:
                state.escalations.append("closely_scored_plans")
                point_label = "point" if finalist_gap == 1 else "points"
                reasons.append(f"The top plans are separated by {finalist_gap} {point_label}.")
            if assessment["confidence"] < 0.75:
                state.escalations.append("low_confidence")
                reasons.append("Confidence is below the release threshold.")
            reason = " ".join(reasons)

        recommendations = summarize_actions(candidate, state.evidence)
        citation_claims = sum(1 for item in recommendations if item["support"])
        guidance_claims = sum(1 for item in recommendations if item["topic_aligned_guidance"])
        citation_coverage = citation_claims / len(recommendations) if recommendations else None
        guidance_alignment = guidance_claims / len(recommendations) if recommendations else None
        result: ForecastResult = {
            "run_id": run_id,
            "decision": decision,
            "decision_reason": reason,
            "human_review_required": decision in {"HUMAN_REVIEW_REQUIRED", "ABSTAIN"},
            "department": scenario.department,
            "location": scenario.location,
            "scenario_status": scenario.scenario_status,
            "forecast_days": scenario.forecast_days,
            "strain": assessment["strain"],
            "risk_score": assessment["score"],
            "confidence": assessment["confidence"],
            "risk_components": assessment["components"],
            "recommendations": recommendations,
            "evidence": [
                {key: item.get(key) for key in ("id", "source", "title", "url", "topic", "score", "last_reviewed", "retrieved_on")}
                for item in state.evidence
            ],
            "finalists": state.candidates,
            "rejected_plans": state.observations.get("rejected_plans", []),
            "tree_search": state.observations.get("tree_search"),
            "escalations": sorted(set(state.escalations)),
            "metrics": {
                "citation_coverage": round(citation_coverage, 3) if citation_coverage is not None else None,
                "topic_aligned_guidance_coverage": round(guidance_alignment, 3) if guidance_alignment is not None else None,
                "finalist_gap": finalist_gap,
            },
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "trace": state.trace,
            "safety_boundary": "Advisory only. No individual diagnosis, fitness-for-duty judgment, dispatch action, schedule change, or automatic mutual-aid request.",
        }
        memory.save_run(run_id, scenario.location, decision, assessment["strain"], assessment["score"])
        return result
    except Exception as error:
        failure_observation = {"error_type": type(error).__name__}
        try:
            memory.log(run_id, "Coordinator Agent", "fail_closed", failure_observation)
        except Exception:
            pass
        if isinstance(error, EvidenceViolation):
            detail = f"EvidenceViolation: {error}"
        else:
            detail = type(error).__name__
        trace = state.trace + [
            {"agent": "Coordinator Agent", "action": "fail_closed", "observation": failure_observation}
        ]
        return _blocked_result(
            run_id,
            f"tool_or_evidence_failure: {detail}",
            (time.perf_counter() - started) * 1000,
            scenario=scenario,
            trace=trace,
        )
    finally:
        memory.close()
