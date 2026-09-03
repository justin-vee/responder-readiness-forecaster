from __future__ import annotations

from typing import Any

from .reasoning import ACTION_CATALOG, beam_search, calculate_readiness
from .retrieval import retrieve
from .schemas import RunState


class EvidenceAgent:
    name = "Evidence Agent"

    def run(self, state: RunState, passages: list[dict[str, Any]]) -> None:
        evidence = retrieve(state.scenario, passages, top_k=4)
        state.evidence = evidence
        state.observe(self.name, "retrieve_guidance", {"results": len(evidence), "ids": [item["id"] for item in evidence]})
        if not evidence:
            state.escalations.append("authoritative_evidence_unavailable")
        if state.scenario.active_weather_alert and not state.scenario.alert_is_current():
            state.escalations.append("weather_alert_stale_or_missing_expiration")


class ReadinessAnalyst:
    name = "Readiness Analyst"

    def run(self, state: RunState) -> None:
        assessment = calculate_readiness(state.scenario)
        state.observations["readiness"] = assessment
        state.observe(self.name, "calculate_readiness", assessment)


class OperationsPlanner:
    name = "Operations Planner"

    def run(self, state: RunState) -> None:
        assessment = state.observations["readiness"]
        if assessment["strain"] == "low":
            state.candidates = []
            state.observe(self.name, "monitor_only", "No intervention plan generated for a low-strain synthetic case.")
            return
        search = beam_search(state.scenario, state.evidence)
        state.candidates = search["finalists"]
        state.observations["tree_search"] = {key: value for key, value in search.items() if key != "trace"}
        state.observations["tree_trace"] = search["trace"]
        state.observe(self.name, "search_response_plans", state.observations["tree_search"])


class SafetyCritic:
    name = "Safety Critic"

    def run(self, state: RunState) -> None:
        if not state.candidates:
            state.observe(self.name, "safety_check", {"accepted": False, "reason": "no_candidate_plan"})
            return
        accepted = []
        rejected = []
        for candidate in state.candidates:
            failures = list(candidate["hard_failures"])
            if candidate["projected_coverage"] < 0.80:
                failures.append("coverage_below_minimum")
            if not candidate["evidence_ids"]:
                failures.append("ungrounded_plan")
            if failures:
                rejected.append({"actions": candidate["actions"], "failures": sorted(set(failures))})
            else:
                accepted.append(candidate)
        state.candidates = accepted
        state.observations["rejected_plans"] = rejected
        state.observe(self.name, "safety_check", {"accepted": len(accepted), "rejected": rejected})


def summarize_actions(candidate: dict[str, Any] | None, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidate:
        return []
    summaries = []
    for action in candidate["actions"]:
        action_topics = ACTION_CATALOG[action]["topics"]
        guidance = []
        for item in evidence:
            searchable = f"{item.get('topic', '')} {item.get('text', '')}".lower()
            if any(topic in searchable for topic in action_topics):
                guidance.append(f"guidance:{item['id']}")
        summaries.append({
            "id": action,
            "label": ACTION_CATALOG[action]["label"],
            "requires_human_approval": ACTION_CATALOG[action]["requires_approval"],
            "support": ["scenario:team_level_inputs", *guidance],
            "topic_aligned_guidance": guidance,
        })
    return summaries
