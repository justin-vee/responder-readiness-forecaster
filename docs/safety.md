# Safety plan

## Intended use and boundaries

The prototype supports team-level readiness and recovery planning for the Cranberry Township, Pennsylvania test case. All demonstration workloads, staffing levels, Guard or Reserve conflicts, and weather conditions are synthetic. The system is advisory only and is not a medical device, fitness-for-duty system, dispatch tool, or autonomous operations system.

## Input controls

- Accept only public, synthetic, or anonymized team-level records.
- Reject free-text notes and unexpected person-level fields, including names, identifiers, medical or disciplinary information, military orders, and private schedules.
- Validate ranges and required fields before reasoning begins.
- Treat an alert as current only when issue and expiration times are present and the scenario's as-of time falls within that window.
- Show the scenario status and as-of time before a user runs the forecast.
- Prefer synthetic data because small-team aggregates can still create re-identification risk.

## Output controls

- Never diagnose burnout or make a fitness-for-duty judgment.
- Never recommend discipline or employment action.
- Label action effects as synthetic heuristics.
- Return evidence identifiers, alternatives, confidence, and unresolved conditions.
- Use `ABSTAIN` when an input or hard safety condition fails.
- Describe low-strain results as monitoring guidance, not as proof that the team or an individual is safe.
- Keep every operational proposal contingent on authorized human approval.

## Action controls

The prototype is read-only. It cannot change schedules, cancel training, contact responders, control dispatch, or request mutual aid. Any operational proposal returns `HUMAN_REVIEW_REQUIRED`.

## Human intervention triggers

- Missing, stale, contradictory, or unavailable evidence
- Private or person-level information
- No candidate that passes the safety critic
- Confidence below the release threshold
- Closely scored plans, defined as a gap of three points or less
- Any operational change involving coverage, mutual aid, training, or staffing
- Active emergency operations, policy ambiguity, or unexpected tool behavior

Established incident command and Butler County 911 operations always take priority.

## Runtime and evidence monitoring

Each run should preserve the scenario as-of time, retrieved evidence identifiers, source URLs, project review dates, confidence, critic findings, decision, and escalation reason. Source ranking is not source verification. A human reviewer must check the live authoritative page before relying on evidence in an operational setting.

## Human reviewer checklist

Before approving any proposal, an authorized leader should confirm that:

- the data are authorized, team-level, and current enough for the decision;
- no person can reasonably be identified from the input or output;
- cited guidance still applies and any weather alert is live;
- minimum coverage and local policy are satisfied;
- incident command, dispatch, and mutual-aid procedures are not displaced; and
- the action is fair, feasible, reversible, and documented.

The human reviewer owns the final decision. Approval should never be inferred from a displayed plan or score.
