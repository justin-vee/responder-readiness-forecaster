from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import run_evaluation
from .orchestrator import run_forecast
from .paths import data_root, default_memory_path
from .schemas import split_harness_controls


DATA_ROOT = data_root()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the advisory responder readiness forecaster.")
    parser.add_argument("--scenario", type=Path, default=DATA_ROOT / "synthetic" / "scenarios" / "high_strain.json")
    parser.add_argument("--knowledge", type=Path, default=DATA_ROOT / "public" / "authoritative_guidance.json")
    parser.add_argument("--memory", type=Path, default=default_memory_path())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    passages = json.loads(args.knowledge.read_text())
    if args.evaluate:
        output = run_evaluation(DATA_ROOT / "synthetic" / "scenarios", passages)
    else:
        scenario, controls = split_harness_controls(json.loads(args.scenario.read_text()))
        knowledge = [] if controls.get("simulate_knowledge_unavailable", False) else passages
        output = run_forecast(scenario, knowledge, args.memory)
    rendered = json.dumps(output, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
