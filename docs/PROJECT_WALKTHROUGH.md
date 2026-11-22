# Project walkthrough

## What the platform does

The platform helps a technology-evaluation team identify open-source data-engineering repositories that combine ecosystem importance with current maintenance activity. GitHub is the analytical dataset; Hacker News is supplemental discussion data; CoinGecko remains a separately modeled source.

## End-to-end flow

1. Airflow runs the three extractors in parallel every day at 06:00 UTC.
2. Extractors land immutable JSON under `raw/<source>/<logical_date>/` in S3.
3. The loader reads the date-scoped files through a Snowflake storage integration.
4. All sources are merged transactionally into RAW tables using deterministic source/date keys.
5. `dbt source freshness` verifies the inputs.
6. `dbt build` creates typed staging views, the incremental repository-day fact, the current momentum mart, and all tests in dependency order.
7. Python/SciPy calculate the documented hypothesis results from the same repository-day grain.
8. A packaged Tableau workbook exposes repository landscape, evaluation ranking, and maintenance risk to stakeholders using an embedded governed extract.

## Important implementation files

| File | Responsibility |
| --- | --- |
| `dags/ecosystem_elt_dag.py` | Schedule, retries, parallelism, and dependencies |
| `dags/extractors/github_extractor.py` | Official API pagination, rate handling, and run metadata |
| `scripts/load_to_snowflake.py` | Storage-integration stage, deterministic merge, transaction, and audit |
| `dbt_project/models/staging/stg_github_repos.sql` | Typed source contract without silently replacing invalid values |
| `dbt_project/models/marts/fct_repo_daily.sql` | Incremental repository/date analytical fact |
| `dbt_project/models/marts/mart_repo_momentum.sql` | Evaluation score, risk, growth, and readiness |
| `analytics/github_intelligence.py` | Local contracts, calculations, statistics, and public evidence collection |
| `scripts/build_portfolio_evidence.py` | Credential-free reproducible reviewer path |

## Grain and replay safety

The declared grain is one `repo_id` per `snapshot_date`. Snowflake derives a stable SHA-256 key from source/table, source record ID, and date. `MERGE` updates a matching snapshot and inserts only a new key. The local acceptance path applies the same batch three times and verifies identical counts and no duplicates.

## Data quality

Python checks required identifiers, key uniqueness, required popularity values, nonnegative observed metrics, valid timestamps, and valid date ordering. dbt adds not-null, unique, accepted-value, nonnegative, date-ordering, freshness, and source/target reconciliation tests.

Missing values remain missing. In particular, an unavailable public issue count is stored as null with a collection status; it is not treated as a genuine zero.

## Analytics

The main analysis compares the proportion of repositories with recent activity between the top star quartile and the remainder. It includes Wilson intervals, absolute effect size, Fisher's exact test, four activity-window definitions, repository-age context, and explicit observational limitations.

The star-growth/future-fork-growth analysis is gated until 14 daily snapshots exist because it requires non-overlapping longitudinal windows.

## Evidence boundary

Local collection, replay behavior, quality checks, Python tests, dbt parsing, results, and Tableau package structure are verified and committed. Snowflake `MERGE` is implemented and unit-tested, but three live Snowflake replays are not claimed. The repository includes a native Tableau workbook and self-contained `.twbx`; hosted Tableau Public deployment and local visual rendering are not claimed.

## Run locally

```bash
python3 -m pip install -r requirements-dev.txt
make verify
```

## Run with cloud services

```bash
docker compose up -d --build
```

Configure `.env`, the Snowflake profile, and the storage integration first. See `SNOWFLAKE_SETUP.sql` and `OPERATIONS_RUNBOOK.md`.
