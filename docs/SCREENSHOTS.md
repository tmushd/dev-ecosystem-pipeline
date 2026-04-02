# Screenshots Checklist (Portfolio)

These screenshots make the project "real" to a recruiter. Save them under `docs/screenshots/` and commit them.

## 1) Airflow (Orchestration Proof)

- DAG list showing `dev_ecosystem_elt`
- DAG graph view with all tasks green:
  - `extract_github`
  - `extract_coingecko`
  - `extract_hackernews`
  - `load_to_snowflake`
  - `dbt_run_staging`
  - `dbt_test`
  - `dbt_run_marts`
- (Optional) Task log snippet showing an S3 key being written and a `COPY INTO` statement

Suggested filenames:

- `airflow_dag_graph_success.png`
- `airflow_task_log_copy_into.png`

## 2) S3 (Raw Landing Zone Proof)

From the AWS console, show objects for a single run date:

- `raw/github/YYYY-MM-DD/repos.json`
- `raw/coingecko/YYYY-MM-DD/markets.json`
- `raw/coingecko/YYYY-MM-DD/price_history.json`
- `raw/hackernews/YYYY-MM-DD/posts.json`

Suggested filename:

- `s3_raw_layout.png`

## 3) Snowflake (Warehouse + Tables Proof)

- Query result for raw counts:

  ```sql
  select 'github' as source, count(*) from dev_ecosystem.raw.raw_github_repos
  union all
  select 'coingecko_markets', count(*) from dev_ecosystem.raw.raw_coingecko_markets
  union all
  select 'coingecko_price_history', count(*) from dev_ecosystem.raw.raw_coingecko_price_history
  union all
  select 'community_posts', count(*) from dev_ecosystem.raw.raw_reddit_posts;
  ```

- Query result for the mart table:

  ```sql
  select * from dev_ecosystem.analytics.fct_ingestion_counts order by source_name;
  ```

Suggested filenames:

- `snowflake_raw_counts.png`
- `snowflake_fct_ingestion_counts.png`

## 4) dbt (Transformation Proof)

One screenshot of a successful dbt run in terminal is enough:

- `dbt_run_success.png`

