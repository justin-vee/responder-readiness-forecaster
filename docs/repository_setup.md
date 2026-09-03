# Recommended GitHub setup

## 1. Review before publishing

Keep the project private during preparation. Confirm that every input and output is public, synthetic, or anonymized. Search for secrets, Office lock files, local databases, private schedules, names, and operational records. The repository includes the MIT License for the software and original project documentation. Review `NOTICE.md` before publication because linked public guidance remains subject to its publishers' terms.

## 2. Initialize and test locally

```bash
git init -b main
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
responder-forecaster --evaluate --output examples/outputs/evaluation_report.json
git add .
git commit -m "Initial capstone release"
```

## 3. Create the remote repository

Recommended name: `responder-readiness-forecaster`.

```bash
gh auth status
gh auth login -h github.com
gh repo create responder-readiness-forecaster --public --source=. --remote=origin --push
```

Run the privacy and secret review before the public command. After publication, place the actual repository URL in the report and on slide 10.

## 4. Branch and release strategy

Protect `main`, use short feature branches, require passing tests, and merge through pull requests. Put large final-report and presentation binaries in a tagged GitHub Release or Git LFS rather than normal Git history. Keep only curated JSON examples in `examples/outputs`.

## 5. Recommended repository settings

- Enable secret scanning and Dependabot alerts.
- Require pull-request checks before merging to `main`.
- Add topics such as `agentic-ai`, `rag`, `tree-of-thought`, `public-safety`, and `human-in-the-loop`.
- Add an issue template for safety or data-quality reports.
- Do not enable automated deployment to an operational environment.
