from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ACTION_CATALOG = {
    "request_mutual_aid": {
        "label": "Request authorized review of mutual-aid coverage",
        "coverage_effect": 0.18,
        "recovery": 6,
        "cost": 3,
        "requires_approval": True,
        "topics": {"staffing"},
    },
    "protect_recovery_window": {
        "label": "Protect a recovery window before another demanding shift",
        "coverage_effect": 0.00,
        "recovery": 12,
        "cost": 2,
        "requires_approval": True,
        "topics": {"fatigue", "hours"},
    },
    "move_outdoor_training": {
        "label": "Consider moving or postponing synthetic outdoor training",
        "coverage_effect": 0.04,
        "recovery": 7,
        "cost": 1,
        "requires_approval": True,
        "topics": {"heat", "weather"},
    },
    "heat_work_rest_cycle": {
        "label": "Use a heat work-rest cycle with water and cooling",
        "coverage_effect": 0.00,
        "recovery": 8,
        "cost": 2,
        "requires_approval": True,
        "topics": {"heat"},
    },
    "rotate_assignments": {
        "label": "Consider rotating demanding assignments across available teams",
        "coverage_effect": 0.05,
        "recovery": 6,
        "cost": 2,
        "requires_approval": True,
        "topics": {"staffing", "fatigue"},
    },
}
ACTION_ORDER = {name: position for position, name in enumerate(ACTION_CATALOG)}


def calculate_readiness(scenario: Any) -> dict[str, Any]:
    components = {
        "incident_load": 1 if scenario.incident_count_72h >= 4 else 0,
        "overnight_disruption": 2 if scenario.overnight_calls_72h >= 2 else 0,
        "extended_shift": 2 if scenario.longest_shift_hours >= 12 else 0,
        "reduced_staffing": 2 if scenario.available_staff_ratio < 0.80 else 0,
        "guard_reserve_availability": 1 if scenario.guard_reserve_conflicts > 0 else 0,
        "current_weather_alert": 1 if scenario.active_weather_alert and scenario.alert_is_current() else 0,
    }
    score = sum(components.values())
    strain = "high" if score >= 7 else "moderate" if score >= 4 else "low"
    confidence = 0.90
    if scenario.active_weather_alert and not scenario.alert_is_current():
        confidence -= 0.25
    return {"score": score, "strain": strain, "confidence": round(confidence, 2), "components": components}


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    depth: int
    actions: tuple[str, ...]
    score: int
    score_breakdown: dict[str, int]
    projected_coverage: float
    evidence_ids: tuple[str, ...]
    hard_failures: tuple[str, ...]


def _canonical(actions: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(actions, key=ACTION_ORDER.get))


def _evidence_topics(evidence: list[dict[str, Any]]) -> set[str]:
    text = " ".join(f"{item.get('topic', '')} {item.get('text', '')}" for item in evidence).lower()
    return {topic for topic in ("fatigue", "hours", "heat", "staffing", "weather", "readiness") if topic in text}


def evaluate_plan(actions: tuple[str, ...], scenario: Any, evidence: list[dict[str, Any]], node_id: str) -> PlanNode:
    projected = min(1.0, scenario.available_staff_ratio + sum(ACTION_CATALOG[action]["coverage_effect"] for action in actions))
    topics = _evidence_topics(evidence)
    action_topics = set().union(*(ACTION_CATALOG[action]["topics"] for action in actions))
    coverage = min(35, round(35 * projected / 0.90))
    recovery = min(25, sum(ACTION_CATALOG[action]["recovery"] for action in actions))
    feasibility = max(0, 15 - sum(ACTION_CATALOG[action]["cost"] for action in actions))
    evidence_score = min(15, 9 + 2 * len(action_topics & topics))
    breakdown = {
        "coverage_and_safety": coverage,
        "recovery_benefit": recovery,
        "feasibility": feasibility,
        "evidence": evidence_score,
        "privacy_fairness_reversibility": 10,
    }
    failures = []
    if len(actions) == 3 and projected < 0.80:
        failures.append("coverage_below_minimum")
    if len(actions) == 3 and scenario.active_weather_alert and scenario.alert_is_current() and "heat" in scenario.active_weather_alert.lower() and "heat_work_rest_cycle" not in actions:
        failures.append("heat_control_missing")
    if scenario.contains_private_person_data:
        failures.append("private_person_data_not_allowed")
    evidence_ids = tuple(item["id"] for item in evidence if item.get("score", 0) > 0)
    return PlanNode(node_id, len(actions), actions, sum(breakdown.values()), breakdown, round(projected, 2), evidence_ids, tuple(failures))


def beam_search(scenario: Any, evidence: list[dict[str, Any]], beam_width: int = 3, depth_limit: int = 3) -> dict[str, Any]:
    frontier: list[tuple[str, ...]] = [()]
    trace: list[PlanNode] = []
    node_counter = 0
    for depth in range(1, depth_limit + 1):
        unique: dict[tuple[str, ...], PlanNode] = {}
        for parent_actions in frontier:
            for action in ACTION_CATALOG:
                if action in parent_actions:
                    continue
                actions = _canonical(parent_actions + (action,))
                node_counter += 1
                node = evaluate_plan(actions, scenario, evidence, f"d{depth}-n{node_counter}")
                trace.append(node)
                if node.hard_failures or node.score < 65:
                    continue
                current = unique.get(actions)
                if current is None or node.score > current.score:
                    unique[actions] = node
        ranked = sorted(unique.values(), key=lambda node: (-node.score, node.actions))
        selected: list[PlanNode] = []

        # Preserve a small amount of safety-relevant branch diversity so the
        # beam does not discard heat or coverage strategies too early.
        required_actions = []
        if scenario.active_weather_alert and scenario.alert_is_current() and "heat" in scenario.active_weather_alert.lower():
            required_actions.append("heat_work_rest_cycle")
        if scenario.available_staff_ratio < 0.80:
            required_actions.append("request_mutual_aid")
        for required in required_actions:
            match = next((node for node in ranked if required in node.actions and node not in selected), None)
            if match:
                selected.append(match)
        fill_pool = ranked
        if depth == depth_limit - 1 and len(required_actions) > 1:
            # One action remains at the next depth. Keep partial plans that
            # already contain at least one required action so they can still
            # become distinct, fully compliant finalists.
            fill_pool = [node for node in ranked if any(required in node.actions for required in required_actions)]
        for node in fill_pool:
            if node not in selected:
                selected.append(node)
            if len(selected) >= beam_width:
                break
        frontier = [node.actions for node in selected[:beam_width]]
        if not frontier:
            break
    finalists = sorted((evaluate_plan(actions, scenario, evidence, f"final-{i+1}") for i, actions in enumerate(frontier)), key=lambda node: (-node.score, node.actions))
    return {
        "strategy": "beam_search",
        "beam_width": beam_width,
        "depth_limit": depth_limit,
        "evaluated_nodes": len(trace),
        "finalists": [asdict(node) for node in finalists],
        "trace": [asdict(node) for node in trace],
        "action_effect_notice": "Coverage and recovery effects are synthetic heuristic values for demonstration only.",
    }
