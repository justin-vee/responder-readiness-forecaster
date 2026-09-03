# Recorded demonstration guide

## GUI demonstration

Launch the local visual interface:

```bash
PYTHONPATH=src python -m responder_forecaster.gui
```

Use the synthetic presets in `data/synthetic/showcase/` to show how the interface behaves across low, moderate, and high strain as well as safe fallback cases. Start with `01_routine_monitoring.json`, compare it with `08_high_heat_training_pressure.json`, and end with `15_missing_staffing_guardrail.json` or `16_private_data_flag_guardrail.json` to demonstrate that the system stops when it should.

Before each run, point out the synthetic-data banner and as-of time. After each run, show the decision, factors, confidence, alternatives, critic findings, evidence publisher and project review date, and human-review status. Explain that any Guard or Reserve conflict and weather alert is fictional. Do not describe a preset as a report about a real responder, unit, station, or current Cranberry Township condition.

## Main run

```bash
PYTHONPATH=src python -m responder_forecaster.cli \
  --scenario data/synthetic/scenarios/high_strain.json \
  --memory .local/demo.sqlite3 \
  --output examples/outputs/high_strain_forecast.json
```

Show these fields in order:

1. `scenario_status`: confirms that the values are synthetic.
2. `decision`: shows `HUMAN_REVIEW_REQUIRED`.
3. `risk_components`: makes the strain score visible.
4. `evidence`: shows the four approved public passages.
5. `finalists`: shows scores of 93 and 90.
6. `metrics.finalist_gap`: shows the three-point escalation trigger.
7. `trace`: shows all five logical roles.

The demonstration must not be described as current Cranberry Township data or a validated operational forecast.

## Evaluation run

```bash
PYTHONPATH=src python -m responder_forecaster.cli \
  --evaluate \
  --output examples/outputs/evaluation_report.json
```

The report covers six synthetic forecast scenarios and three deliberately unsafe critic cases. Explain that the results are deterministic software-behavior checks. They do not establish predictive validity.

The 16 showcase presets are intentionally excluded from this graded evaluation. This keeps the six-case baseline stable while providing more varied GUI examples.

## Safe fallback examples

- `missing_data.json` returns `ABSTAIN`.
- `privacy_violation.json` returns `ABSTAIN`.
- `stale_alert.json` returns `HUMAN_REVIEW_REQUIRED` with no plan.
- `knowledge_unavailable.json` returns `HUMAN_REVIEW_REQUIRED` with no unsupported plan.
