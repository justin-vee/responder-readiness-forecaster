# Contributing

Use short feature branches and open a pull request into `main`. Every change should include relevant tests and must preserve the public/synthetic data boundary.

Before requesting review, run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m responder_forecaster.cli --evaluate
```

Do not commit generated local memory databases, secrets, Office deliverables, or private responder information.
