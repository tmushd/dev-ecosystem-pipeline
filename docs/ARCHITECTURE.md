# Architecture and engineering decisions

## Objective

The system produces trusted repository-day facts and a current technology-evaluation queue. GitHub is the analytical domain. Hacker News is a supplemental discussion feed, and CoinGecko remains an independently supported ingestion example rather than being forced into a misleading relationship with software activity.

## Flow

1. Airflow launches three source extractors in parallel each day.
2. Extractors write immutable JSON into `raw/<source>/<logical_date>/` and attach run ID, extraction time, source, and schema version.
3. Snowflake uses an S3 storage integration. The loader merges all four objects inside one transaction using deterministic snapshot keys.
4. dbt casts source variants into documented fields, applies schema/business tests, reconciles counts, and incrementally publishes `fct_repo_daily`.
5. `mart_repo_momentum` calculates deltas, recency, transparent ranking, maintenance risk, and longitudinal-analysis readiness.
6. SQL, the packaged Tableau executive dashboard, and the hypothesis report consume the same governed facts.

## Reliability semantics

The repository/date grain is declared at ingestion rather than repaired later. Snowflake `MERGE` prevents replay duplicates; the local acceptance test applies the same batch three times and obtains 50 rows after every replay. The source partition, warehouse transaction, dbt unique test, and release check each enforce the grain independently.

`PIPELINE_RUN_AUDIT` records source, date, run ID, target, affected rows, time, and status. dbt source freshness warns at 36 hours and errors at 72. Airflow allows one active run, retries failures three times, and bounds task execution to 45 minutes.

## Security

The external stage references a Snowflake `STORAGE_INTEGRATION`; AWS access keys are never embedded in generated SQL. `.env` is ignored, logs do not print secrets, and setup grants runtime access through a least-privilege project role. In production, use key-pair or workload-identity authentication for Snowflake rather than a password.

## Local evidence path

Cloud credentials should not be required to review analytical claims. `scripts/build_portfolio_evidence.py` collects a bounded live public snapshot, writes raw and curated artifacts, performs three replays, runs quality checks and hypotheses, and creates the dashboard. The production extractor still uses the official GitHub API; the reviewer path falls back to public HTML when unauthenticated API quota is exhausted.

## Known limits

- GitHub search returns a selected ecosystem sample, not a probability sample.
- A push/commit is an imperfect maintenance proxy.
- The public evidence collector depends on GitHub page markup and is therefore not the production ingestion path.
- Momentum inference remains disabled until enough daily observations exist.
