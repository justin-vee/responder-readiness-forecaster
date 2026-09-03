# Evaluation

The evaluation suite contains six synthetic cases: high strain, low strain, private data, missing data, stale alert, and unavailable knowledge. It measures:

- Decision accuracy against the expected synthetic outcome
- Strain classification accuracy where an expected class exists
- Mandatory-escalation recall
- Recommendation citation coverage and topic-aligned guidance coverage
- Hard safety violations
- Safety Critic rejection of three deliberately unsafe plans
- Safe fallback behavior
- Mean local execution latency

The repository also includes sixteen unlabeled showcase cases. They exercise a wider range of low, moderate, high, stale-alert, missing-data, and privacy-boundary behavior without being counted as accuracy examples. The batch evaluator reports labeled and unlabeled denominators separately, plus load errors, mean and p95 latency, wall-clock time, and local throughput.

Fifty-five automated tests cover the stable response contract, timestamps, finite and boundary values, string limits, every packaged JSON file, all sixteen showcase outcomes, evidence allowlisting, fail-closed memory behavior, concurrent SQLite runs, batch evaluation, local GUI assets and routes, same-origin enforcement, request saturation, malformed browser requests, path traversal attempts, concurrent browser requests, and synthetic showcase execution.

Targets are 100% structural citation coverage, 100% topic-aligned guidance coverage for released recommendations, zero hard safety violations, at least 95% unsafe-plan detection, and 100% recognition of mandatory escalation triggers.

Citation coverage confirms that support identifiers are attached. Topic alignment checks action topics against retrieved passages. Neither metric proves that an expert agrees with the recommendation. These targets and the current deterministic results are software-behavior checks. They do not demonstrate predictive validity, health outcomes, or operational effectiveness. Field deployment would require a larger labeled benchmark, historical backtesting, calibration, threshold review, failure testing, and prospective user evaluation.
