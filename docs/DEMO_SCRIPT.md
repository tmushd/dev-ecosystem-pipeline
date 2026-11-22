# Recruiter demo script (90 seconds)

## 1. Lead with the decision

“I built an analytics platform that helps a technology-evaluation team prioritize open-source data-engineering repositories using popularity, maintenance recency, and longitudinal readiness.”

## 2. Show the architecture

Open the README diagram and explain:

- Airflow schedules parallel API extraction.
- S3 preserves replayable date partitions.
- Snowflake merges deterministic repository/date snapshots atomically.
- dbt freshness and `dbt build` publish tested facts and marts.
- Python/SciPy and Plotly turn the facts into evidence and a decision interface.

## 3. Show reliability evidence

Open `outputs/reports/latest_run_manifest.json`:

- 50 live repositories.
- Three replays: 50, 50, 50.
- Zero duplicates.
- 10/10 quality gates.
- Source SHA-256 and run metadata.

Point out that unavailable issue counts remain null, not zero.

## 4. Show the analytical finding

Open `docs/ANALYTICAL_FINDINGS.md`:

- Top-star group recent-maintenance rate: 84.6%.
- Remaining group: 40.5%.
- Difference: 44.1 points.
- Fisher p-value: 0.0092.
- The direction remains positive across 14-, 30-, 60-, and 90-day definitions.

State that the sample is selected and observational, so the result supports prioritization—not causality.

## 5. Close with the decision output

Open the dashboard or `mart_repo_momentum.csv` and explain how `ACTIVE`, `WATCH`, `HIGH`, and `COLLECTING_HISTORY` change the next action for an evaluator.

Finish with: “The strongest part of this project is that every headline claim links to a committed artifact, and the README clearly distinguishes local proof from cloud-ready implementation.”
