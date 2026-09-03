# Responder Readiness and Recovery Forecaster

This capstone is a runnable, advisory multi-agent prototype that forecasts **team-level operational strain** for volunteer fire and EMS planning. Cranberry Township, Pennsylvania is the standing test case. Public organizational facts are real; every workload, staffing, alert, recovery, and Guard or Reserve value in the demonstration is synthetic.

The system does **not** diagnose burnout, judge fitness for duty, use private responder records, control dispatch, change schedules, contact responders, or request mutual aid. Consequential recommendations always require an authorized human decision.

## What the prototype demonstrates

- Read-only tool calls with structured observations
- A ReAct-style understand, act, observe, and update trace
- DPR-inspired transparent retrieval with separate query and passage weights
- Short-term trace memory and aggregate long-term SQLite run memory
- Bounded Tree-of-Thought beam search with a visible scoring rubric
- Five roles: Coordinator, Evidence Agent, Readiness Analyst, Operations Planner, and Safety Critic
- Input guardrails, stale-source checks, fail-closed fallback, and explicit human-review gates
- A six-case synthetic evaluation suite plus three deliberately unsafe critic tests
- A local browser-based GUI with sixteen additional synthetic showcase cases
- Fifty-five automated tests covering the forecasting engine, every packaged dataset, boundary values, concurrency, GUI endpoints, and browser-request security

The prototype intentionally uses the Python standard library so reviewers can run it without API keys. CrewAI, LangChain, and MCP remain production integration options; the current code implements their planned role, control-flow, and shared-state responsibilities directly and transparently.

## Quick start

### Visual interface

The easiest way to explore the prototype is the local web interface. It uses only the Python standard library, opens in a browser, and remains available only on the local computer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
responder-forecaster-gui
```

Without installation:

```bash
PYTHONPATH=src python -m responder_forecaster.gui
```

The GUI provides plain-language inputs, quick-start examples, sixteen synthetic presets, changed-input warnings, decision and risk summaries, plan comparison, authoritative evidence links, the five-agent trace, downloadable JSON, and a synthetic batch showcase whose rows can be reopened for closer review. See `docs/gui_user_guide.md` before using it.

### Command line

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
responder-forecaster --output examples/outputs/high_strain_forecast.json
responder-forecaster --evaluate --output examples/outputs/evaluation_report.json
python -m unittest discover -s tests -v
```

Without installation:

```bash
PYTHONPATH=src python -m responder_forecaster.cli --output examples/outputs/high_strain_forecast.json
PYTHONPATH=src python -m responder_forecaster.cli --evaluate --output examples/outputs/evaluation_report.json
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Decision contract

- `ADVISORY`: monitoring guidance only; no operational change is proposed.
- `HUMAN_REVIEW_REQUIRED`: evidence supports one or more options, but an authorized leader must decide.
- `ABSTAIN`: required data or safety conditions failed; the agent provides no plan.

## Repository map

- `src/responder_forecaster/`: agents, retrieval, reasoning, memory, orchestration, and CLI
- `data/public/`: paraphrased authoritative public guidance with provenance
- `data/synthetic/scenarios/`: synthetic normal, high-strain, stale, missing, privacy, and fallback cases
- `data/synthetic/showcase/`: sixteen additional synthetic GUI demonstration cases
- `tests/`: safety, memory, fallback, and integration tests
- `examples/outputs/`: curated demonstration and evaluation results
- `docs/`: architecture, safety, evaluation, and repository publishing guidance

## Important limitations

The readiness thresholds and action effects are illustrative. The retrieval layer is DPR-inspired but is not a trained DPR model. The synthetic evaluation results demonstrate expected software behavior, not predictive validity or real-world safety. A controlled pilot would require department-approved thresholds, live-source freshness checks, historical backtesting, calibration, privacy review, and user testing.

## License and source notices

The software and original project documentation are available under the MIT License. See `LICENSE`. Public guidance and linked source material remain subject to their publishers' terms; see `NOTICE.md`. The license does not represent validation or authorization for operational public-safety use.
