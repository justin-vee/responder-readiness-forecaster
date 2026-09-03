from __future__ import annotations

import math
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse


class EvidenceViolation(ValueError):
    """Raised when an evidence record is malformed or outside the source allowlist."""


REQUIRED_PASSAGE_FIELDS = {"id", "source", "title", "url", "topic", "last_reviewed", "retrieved_on", "text"}
APPROVED_SOURCES = {
    "CDC/NIOSH",
    "National Weather Service",
    "U.S. Fire Administration",
    "Defense Health Agency",
    "Cranberry Township",
    "Cranberry Township EMS",
    "Butler County, Pennsylvania",
}
APPROVED_DOMAINS = {
    "cdc.gov",
    "www.cdc.gov",
    "weather.gov",
    "www.weather.gov",
    "usfa.fema.gov",
    "www.usfa.fema.gov",
    "health.mil",
    "www.health.mil",
    "cranberrytownship.org",
    "www.cranberrytownship.org",
    "cranberrytownshipems.org",
    "www.cranberrytownshipems.org",
    "butlercountypa.gov",
    "www.butlercountypa.gov",
}


CONCEPTS = {
    "fatigue": {"fatigue", "sleep", "overnight", "recovery", "rest"},
    "hours": {"shift", "hours", "extended", "long", "schedule"},
    "heat": {"heat", "hot", "warning", "hydration", "cooling"},
    "staffing": {"staff", "staffing", "coverage", "available", "mutual", "aid"},
    "stress": {"stress", "traumatic", "psychological", "incident"},
    "readiness": {"readiness", "guard", "reserve", "duty", "performance"},
    "weather": {"weather", "alert", "warning", "watch", "advisory", "storm"},
}

QUERY_WEIGHTS = {"fatigue": 1.4, "hours": 1.3, "heat": 1.4, "staffing": 1.4, "stress": 1.0, "readiness": 1.2, "weather": 1.3}
PASSAGE_WEIGHTS = {"fatigue": 1.3, "hours": 1.1, "heat": 1.3, "staffing": 1.0, "stress": 1.1, "readiness": 1.2, "weather": 1.2}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def concept_vector(text: str, weights: dict[str, float]) -> list[float]:
    tokens = set(normalize(text).split())
    return [sum(1.0 for term in terms if term in tokens) * weights[name] for name, terms in CONCEPTS.items()]


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def scenario_queries(scenario: Any) -> list[str]:
    return [
        f"Workload {scenario.incident_count_72h} incidents {scenario.overnight_calls_72h} overnight calls {scenario.longest_shift_hours} hour shift",
        f"Capacity {scenario.available_staff_ratio:.0%} staffing Guard Reserve conflicts {scenario.guard_reserve_conflicts}",
        f"Environment {scenario.location} weather alert {scenario.active_weather_alert}",
    ]


def validate_passages(passages: Any) -> list[dict[str, Any]]:
    if not isinstance(passages, list):
        raise EvidenceViolation("evidence_corpus_must_be_a_list")
    validated = []
    seen_ids = set()
    for index, passage in enumerate(passages):
        if not isinstance(passage, dict):
            raise EvidenceViolation(f"evidence_record_{index}_must_be_an_object")
        missing = sorted(REQUIRED_PASSAGE_FIELDS - set(passage))
        if missing:
            raise EvidenceViolation(f"evidence_record_{index}_missing_fields: {', '.join(missing)}")
        unexpected_collections = [key for key, value in passage.items() if isinstance(value, (dict, list, tuple, set))]
        if unexpected_collections:
            raise EvidenceViolation(f"evidence_record_{index}_nested_values_not_allowed")
        if passage["source"] not in APPROVED_SOURCES:
            raise EvidenceViolation(f"source_not_approved: {passage['source']}")
        parsed = urlparse(str(passage["url"]))
        if parsed.scheme != "https" or parsed.netloc.lower() not in APPROVED_DOMAINS:
            raise EvidenceViolation(f"source_url_not_approved: {passage['url']}")
        for field in ("last_reviewed", "retrieved_on"):
            try:
                parsed_date = date.fromisoformat(str(passage[field]))
            except ValueError as error:
                raise EvidenceViolation(f"invalid_{field}: {passage[field]}") from error
            if parsed_date > date.today():
                raise EvidenceViolation(f"future_{field}: {passage[field]}")
        if not all(str(passage[field]).strip() for field in REQUIRED_PASSAGE_FIELDS):
            raise EvidenceViolation(f"evidence_record_{index}_contains_blank_required_value")
        if passage["id"] in seen_ids:
            raise EvidenceViolation(f"duplicate_evidence_id: {passage['id']}")
        seen_ids.add(passage["id"])
        validated.append(passage)
    return validated


def retrieve(scenario: Any, passages: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    passages = validate_passages(passages)
    if not passages:
        return []
    query_vectors = [concept_vector(query, QUERY_WEIGHTS) for query in scenario_queries(scenario)]
    query = [sum(column) / len(query_vectors) for column in zip(*query_vectors)]
    ranked = []
    for passage in passages:
        searchable = f"{passage.get('topic', '')} {passage.get('text', '')}"
        score = cosine(query, concept_vector(searchable, PASSAGE_WEIGHTS))
        if score > 0:
            ranked.append({**passage, "score": round(score, 3)})
    ranked.sort(key=lambda item: (-item["score"], item["id"]))

    # Preserve one passage for each active operational concern before filling
    # remaining slots by score. This avoids allowing several similar heat
    # passages to crowd out staffing or fatigue evidence.
    required_topics = []
    if scenario.active_weather_alert:
        required_topics.extend(["weather", "heat"])
    if scenario.available_staff_ratio < 0.80:
        required_topics.append("staffing")
    if scenario.overnight_calls_72h >= 2 or scenario.longest_shift_hours >= 12:
        required_topics.append("fatigue")
    selected = []
    preferred_sources = {
        "weather": {"National Weather Service"},
        "heat": {"CDC/NIOSH"},
        "staffing": {"Cranberry Township", "Butler County, Pennsylvania", "Cranberry Township EMS"},
        "fatigue": {"CDC/NIOSH", "U.S. Fire Administration"},
    }
    for topic in required_topics:
        matches = [
            item for item in ranked
            if topic in f"{item.get('topic', '')} {item.get('text', '')}".lower() and item not in selected
        ]
        match = next((item for item in matches if item["source"] in preferred_sources.get(topic, set())), None)
        match = match or (matches[0] if matches else None)
        if match:
            selected.append(match)
        if len(selected) >= top_k:
            return selected
    for item in ranked:
        if item not in selected:
            selected.append(item)
        if len(selected) >= top_k:
            break
    return selected
