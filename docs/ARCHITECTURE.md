# Architecture

This project is an ELT pipeline:

APIs -> S3 (raw landing zone) -> Snowflake RAW (COPY INTO) -> dbt -> Snowflake ANALYTICS

## Why S3 in the Middle?

S3 is acting like a "data lake landing zone":

- Raw API responses are stored immutably by run date.
- Loads into Snowflake can be replayed from S3 if needed.
- Snowflake ingestion uses `COPY INTO` (a production-style pattern).

## S3 Layout

```text
s3://<bucket>/
  raw/
    github/YYYY-MM-DD/repos.json
    coingecko/YYYY-MM-DD/markets.json
    coingecko/YYYY-MM-DD/price_history.json
    hackernews/YYYY-MM-DD/posts.json
```

## Snowflake Objects

- Warehouse: `DEV_ECOSYSTEM_WH`
- Database: `DEV_ECOSYSTEM`
- Schemas:
  - `RAW` (landing tables)
  - `ANALYTICS` (dbt models)

RAW tables (JSON stored in `VARIANT`):

- `RAW.RAW_GITHUB_REPOS`
- `RAW.RAW_COINGECKO_MARKETS`
- `RAW.RAW_COINGECKO_PRICE_HISTORY`
- `RAW.RAW_REDDIT_POSTS` (currently contains Hacker News posts; name kept to avoid changing dbt)

External stage:

- `RAW.S3_STAGE` pointing to your S3 bucket root (`s3://<bucket>`)

## Data Flow (Airflow DAG)

`extract_github`, `extract_coingecko`, `extract_hackernews` run in parallel:

1. Extract raw JSON from the API
2. Upload JSON to S3 under `raw/<source>/<run_date>/...`
3. Load task uses Snowflake `COPY INTO` from the S3 stage into RAW tables
4. dbt builds staging views and a mart table (`ANALYTICS.fct_ingestion_counts`)

