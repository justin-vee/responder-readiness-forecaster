from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any, Literal, TypedDict


class InputViolation(ValueError):
    """Raised when an input violates the public/synthetic team-level boundary."""


# Fields that steer the evaluation harness rather than describe the team.
# They never reach Scenario, so the strict unexpected-field guard still
# rejects anything genuinely unknown.
HARNESS_CONTROL_FIELDS = {
    "simulate_knowledge_unavailable",
    "showcase_only",
    "evaluation_enabled",
}


def split_harness_controls(raw: Any) -> tuple[Any, dict[str, Any]]:
    """Split a raw scenario into its payload and its harness control fields.

    Both the CLI and the evaluation harness call this, so one fixture yields
    the same decision through either entry point.
    """
    if not isinstance(raw, Mapping):
        return raw, {}
    payload = {key: value for key, value in raw.items() if key not in HARNESS_CONTROL_FIELDS}
    controls = {key: value for key, value in raw.items() if key in HARNESS_CONTROL_FIELDS}
    return payload, controls


PRIVATE_KEYS = {
    "name",
    "responder_name",
    "responder_id",
    "medical_notes",
    "diagnosis",
    "disciplinary_record",
    "military_orders",
    "unit_details",
}

ALLOWED_SCENARIO_STATUSES = {
    "Synthetic test data",
    "Synthetic test data; not a statement of current local conditions",
    "Public team-level data",
    "Anonymized team-level data",
}

ALLOWED_STRAINS = {"low", "moderate", "high"}
ALLOWED_DECISIONS = {"ADVISORY", "HUMAN_REVIEW_REQUIRED", "ABSTAIN"}

Decision = Literal["ADVISORY", "HUMAN_REVIEW_REQUIRED", "ABSTAIN"]


class ForecastResult(TypedDict):
    """Stable response contract shared by the CLI, GUI, and evaluation code."""

    run_id: str
    decision: Decision
    decision_reason: str
    human_review_required: bool
    department: str | None
    location: str | None
    scenario_status: str | None
    forecast_days: int | None
    strain: str
    risk_score: int
    confidence: float
    risk_components: dict[str, int]
    recommendations: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    finalists: list[dict[str, Any]]
    rejected_plans: list[dict[str, Any]]
    tree_search: dict[str, Any] | None
    escalations: list[str]
    metrics: dict[str, float | int | None]
    latency_ms: float
    trace: list[dict[str, Any]]
    safety_boundary: str

SENSITIVE_TEXT_PATTERNS = {
    "medical_or_diagnostic_detail": r"\b(medical|diagnos(?:is|ed|tic)|medication|patient record|health record)\b",
    "disciplinary_detail": r"\b(disciplin(?:e|ary)|performance review|fitness for duty)\b",
    "military_detail": r"\b(military orders?|unit details?|deployment orders?)\b",
    "private_schedule": r"\b(private|personal) schedule\b",
    "named_responder": r"\b(responder|firefighter|emt|paramedic)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
}

REQUIRED_FIELDS = {
    "department",
    "location",
    "scenario_status",
    "forecast_days",
    "incident_count_72h",
    "overnight_calls_72h",
    "longest_shift_hours",
    "available_staff_ratio",
    "guard_reserve_conflicts",
}

STRING_LIMITS = {
    "department": 120,
    "location": 160,
    "scenario_status": 100,
    "active_weather_alert": 120,
    "alert_issued_at": 64,
    "alert_expires_at": 64,
    "as_of": 64,
    "expected_strain": 32,
    "expected_decision": 32,
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class Scenario:
    department: str
    location: str
    scenario_status: str
    forecast_days: int
    incident_count_72h: int
    overnight_calls_72h: int
    longest_shift_hours: float
    available_staff_ratio: float
    guard_reserve_conflicts: int
    active_weather_alert: str = ""
    alert_issued_at: str | None = None
    alert_expires_at: str | None = None
    as_of: str = "2026-08-26T12:00:00-04:00"
    outdoor_training_scheduled: bool = False
    contains_private_person_data: bool = False
    expected_strain: str | None = None
    expected_decision: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Scenario":
        if not isinstance(raw, Mapping):
            raise InputViolation("scenario_must_be_an_object")
        if any(not isinstance(key, str) for key in raw):
            raise InputViolation("scenario_field_names_must_be_strings")
        lowered = {key.lower() for key in raw}
        private_found = sorted(lowered & PRIVATE_KEYS)
        if raw.get("contains_private_person_data") or private_found:
            details = ", ".join(private_found) if private_found else "private-person flag"
            raise InputViolation(f"private_person_data_not_allowed: {details}")

        missing = sorted(REQUIRED_FIELDS - set(raw))
        if missing:
            raise InputViolation(f"missing_required_fields: {', '.join(missing)}")

        allowed = set(cls.__dataclass_fields__)
        unexpected = sorted(set(raw) - allowed)
        if unexpected:
            raise InputViolation(f"unexpected_fields_not_allowed: {', '.join(unexpected)}")

        required_strings = {"department", "location", "scenario_status", "as_of"}
        optional_strings = {"active_weather_alert", "alert_issued_at", "alert_expires_at", "expected_strain", "expected_decision"}
        integer_fields = {"forecast_days", "incident_count_72h", "overnight_calls_72h", "guard_reserve_conflicts"}
        numeric_fields = {"longest_shift_hours", "available_staff_ratio"}
        boolean_fields = {"outdoor_training_scheduled", "contains_private_person_data"}
        for key in required_strings:
            if key in raw and (not isinstance(raw[key], str) or not raw[key].strip()):
                raise InputViolation(f"{key}_must_be_a_nonempty_string")
        for key in optional_strings:
            if key in raw and raw[key] is not None and not isinstance(raw[key], str):
                raise InputViolation(f"{key}_must_be_a_string_or_null")
        for key in integer_fields:
            if key in raw and (isinstance(raw[key], bool) or not isinstance(raw[key], int)):
                raise InputViolation(f"{key}_must_be_an_integer")
        for key in numeric_fields:
            if key in raw and (isinstance(raw[key], bool) or not isinstance(raw[key], (int, float))):
                raise InputViolation(f"{key}_must_be_numeric")
            if key in raw and not math.isfinite(float(raw[key])):
                raise InputViolation(f"{key}_must_be_finite")
        for key in boolean_fields:
            if key in raw and not isinstance(raw[key], bool):
                raise InputViolation(f"{key}_must_be_boolean")

        for key, value in raw.items():
            if isinstance(value, (dict, list, tuple, set)):
                raise InputViolation(f"nested_or_collection_value_not_allowed: {key}")
            if isinstance(value, str):
                limit = STRING_LIMITS.get(key)
                if limit is not None and len(value) > limit:
                    raise InputViolation(f"{key}_exceeds_{limit}_characters")
                for label, pattern in SENSITIVE_TEXT_PATTERNS.items():
                    if re.search(pattern, value, flags=re.IGNORECASE):
                        raise InputViolation(f"sensitive_text_not_allowed: {key}:{label}")

        scenario = cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw})
        if scenario.scenario_status not in ALLOWED_SCENARIO_STATUSES:
            raise InputViolation("scenario_status_must_be_public_synthetic_or_anonymized")
        if scenario.expected_strain is not None and scenario.expected_strain not in ALLOWED_STRAINS:
            raise InputViolation("expected_strain_not_supported")
        if scenario.expected_decision is not None and scenario.expected_decision not in ALLOWED_DECISIONS:
            raise InputViolation("expected_decision_not_supported")
        if not 1 <= scenario.forecast_days <= 30:
            raise InputViolation("forecast_days_out_of_range")
        for name in ("incident_count_72h", "overnight_calls_72h", "guard_reserve_conflicts"):
            if getattr(scenario, name) < 0:
                raise InputViolation(f"{name}_must_be_nonnegative")
        if not 0 <= scenario.longest_shift_hours <= 48:
            raise InputViolation("longest_shift_hours_out_of_range")
        if not 0 <= scenario.available_staff_ratio <= 1:
            raise InputViolation("available_staff_ratio_out_of_range")
        if scenario.overnight_calls_72h > scenario.incident_count_72h:
            raise InputViolation("overnight_calls_cannot_exceed_incident_count")

        timestamps = {
            "as_of": scenario.as_of,
            "alert_issued_at": scenario.alert_issued_at,
            "alert_expires_at": scenario.alert_expires_at,
        }
        parsed_timestamps: dict[str, datetime | None] = {}
        for name, value in timestamps.items():
            try:
                parsed_timestamps[name] = parse_time(value)
            except (TypeError, ValueError) as error:
                raise InputViolation(f"invalid_timestamp: {name}") from error
        if parsed_timestamps["as_of"] is None:
            raise InputViolation("as_of_must_be_a_valid_timestamp")
        if not scenario.active_weather_alert and any(
            parsed_timestamps[name] is not None for name in ("alert_issued_at", "alert_expires_at")
        ):
            raise InputViolation("alert_timestamps_require_active_weather_alert")
        issued = parsed_timestamps["alert_issued_at"]
        expires = parsed_timestamps["alert_expires_at"]
        if issued is not None and expires is not None and issued > expires:
            raise InputViolation("alert_issued_at_cannot_follow_expiration")
        return scenario

    def alert_is_current(self) -> bool:
        if not self.active_weather_alert:
            return True
        issued = parse_time(self.alert_issued_at)
        expires = parse_time(self.alert_expires_at)
        as_of = parse_time(self.as_of)
        return bool(issued and expires and as_of and issued <= as_of <= expires)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunState:
    run_id: str
    scenario: Scenario | None = None
    observations: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, agent: str, action: str, observation: Any) -> None:
        self.trace.append({"agent": agent, "action": action, "observation": observation})
