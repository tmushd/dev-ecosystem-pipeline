# Project Walkthrough (A to Z)

This doc explains the project like you would in a real job: what each tool does, how the pieces connect, what files matter, and how the data flows end-to-end.

## 1) The Big Idea (ELT)

We built an **ELT** pipeline:

- **E**xtract: pull data from external APIs
- **L**oad: store the raw data in the warehouse (Snowflake)
- **T**ransform: model/clean/reshape inside the warehouse (dbt)

Architecture:

APIs -> S3 (raw landing zone) -> Snowflake (COPY INTO) -> dbt -> Analytics

Why this is "real-world":

- You land raw data in object storage (S3) for durability and replay.
- Snowflake loads from S3 using `COPY INTO`, which is a production ingestion pattern.
- dbt owns the SQL transformations so you have a clean, version-controlled modeling layer.

## 2) Repository Layout (What Each Folder Does)

Top-level:

- `dags/`: Airflow DAG + extractors (the orchestration entrypoint)
- `scripts/`: helper scripts for local runs (extract-only, load-only, sanity checks)
- `dbt_project/`: dbt models + config
- `docs/`: architecture, interview prep, and screenshots
- `docker-compose.yaml`: runs Airflow + Postgres locally
- `Dockerfile.airflow`: builds an Airflow image with our Python dependencies
- `.env.example`: template for your real `.env` (secrets)
- `.env` (not committed): your real credentials (secrets)

### 2.1 Airflow files

- `dags/ecosystem_elt_dag.py`
  - Defines the DAG `dev_ecosystem_elt`
  - Creates tasks and dependencies
  - Runs: extract (parallel) -> load -> dbt staging -> dbt tests -> dbt marts

- `dags/extractors/`
  - `github_extractor.py`: calls GitHub REST API, handles pagination + rate limits, uploads JSON to S3
  - `coingecko_extractor.py`: calls CoinGecko endpoints (markets + price history), retries on 429/5xx, uploads JSON to S3
  - `hackernews_extractor.py`: calls Hacker News API (no auth), retries transient failures, uploads JSON to S3
  - `s3_utils.py`: a tiny library that does the actual S3 upload with boto3

### 2.2 Snowflake loader

- `scripts/load_to_snowflake.py`
  - Connects to Snowflake using env vars
  - Ensures `RAW` schema + RAW tables exist
  - Creates an external stage pointing at your S3 bucket
  - Runs `COPY INTO` to load JSON from S3 into RAW tables
  - Stores the filename (`METADATA$FILENAME`) in `source_file` for lineage

### 2.3 dbt models

- `dbt_project/dbt_project.yml`
  - Sets the dbt profile name and default materializations:
    - staging models: `view`
    - marts models: `table`

- `dbt_project/models/staging/sources.yml`
  - Declares the RAW tables as dbt sources (`schema: RAW`)

- `dbt_project/models/staging/*.sql`
  - Creates staging views that currently just expose `raw_data`
  - Example: `stg_github_repos.sql` selects `raw_data` from `RAW.RAW_GITHUB_REPOS`

- `dbt_project/models/marts/fct_ingestion_counts.sql`
  - Creates `ANALYTICS.fct_ingestion_counts`
  - A simple "proof" mart: counts rows per source

### 2.4 Docker / local runtime

- `docker-compose.yaml`
  - Starts 3 services:
    - `postgres`: Airflow metadata database (NOT your analytics database)
    - `airflow-webserver`: Airflow UI on port 8080
    - `airflow-scheduler`: runs the DAG tasks and also serves task logs
  - Mounts local code into the containers:
    - `./dags` -> `/opt/airflow/dags`
    - `./scripts` -> `/opt/airflow/scripts`
    - `./dbt_project` -> `/opt/airflow/dbt_project`
  - Reads credentials from `.env` via `env_file: - .env`

- `Dockerfile.airflow`
  - Builds an Airflow image and installs Python deps from `requirements-airflow.txt`
  - This is why dbt works inside the container even if it's not installed on your laptop

## 3) The `.env` File (How Credentials Connect Everything)

The `.env` file is just `KEY=value` lines. It is not committed to git.

It powers the whole pipeline:

- Docker Compose loads `.env` and injects those variables into Airflow containers.
- Extractors read env vars with `os.getenv(...)`.
- boto3 reads AWS env vars automatically (access key, secret, region).
- Snowflake connector reads Snowflake env vars to connect.
- dbt `profiles.yml` reads Snowflake env vars via `env_var(...)`.

Key env vars used:

- AWS:
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`
- Snowflake:
  - `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`
  - `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`
- APIs:
  - `GITHUB_TOKEN` (CoinGecko + Hacker News are open in this project)

## 4) How the Data Moves (Runtime Flow)

When you trigger the DAG in Airflow:

1. Airflow Scheduler starts each extract task in parallel.
2. Each extractor:
   - Calls its API
   - Builds a Python list/dict payload
   - Calls `upload_json_to_s3(data=..., key=...)` to store a JSON file in S3
3. The load task runs:
   - Creates/updates `RAW.S3_STAGE` in Snowflake pointing at your bucket root
   - Runs `COPY INTO RAW.<table>` from the exact S3 key for that run date
4. dbt runs in the container:
   - Staging views are created in `ANALYTICS`
   - The mart table `ANALYTICS.fct_ingestion_counts` is created/updated

### How does Airflow decide the "run date" folder?

In `dags/ecosystem_elt_dag.py`, we pass `run_date="{{ ds }}"` into the Python extract functions.

- `{{ ds }}` is an Airflow template variable that resolves to the logical run date in `YYYY-MM-DD`.
- That run date becomes part of the S3 key:
  - `raw/github/<ds>/repos.json`
  - `raw/coingecko/<ds>/markets.json`
  - `raw/hackernews/<ds>/posts.json`

## 5) Where Exactly We Upload to S3

The upload happens in `dags/extractors/s3_utils.py`:

- Creates an S3 client: `boto3.client("s3", region_name=AWS_REGION)`
- Serializes Python objects to JSON bytes: `json.dumps(data).encode("utf-8")`
- Writes the object:
  - `Bucket = S3_BUCKET_NAME`
  - `Key = raw/<source>/<run_date>/<file>.json`
  - `Body = <json bytes>`

This is why your Airflow logs show lines like:

`Uploading raw JSON to s3://<bucket>/raw/hackernews/2026-04-02/posts.json`

## 6) Snowflake: Why We Needed a Warehouse + Database + Stage

Concepts:

- **Warehouse**: the compute engine (you pay when it runs queries)
- **Database**: top-level container for schemas/tables
- **Schema**: namespace inside a database (RAW vs ANALYTICS)
- **Stage**: a pointer to external files (S3) that Snowflake can read

We created:

- `DEV_ECOSYSTEM_WH` (warehouse)
- `DEV_ECOSYSTEM` (database)
- `RAW` schema (tables with raw JSON)
- `ANALYTICS` schema (dbt models)
- `RAW.S3_STAGE` (external stage pointing at `s3://<bucket>`)

The key ingestion SQL pattern (simplified):

- `COPY INTO RAW.RAW_GITHUB_REPOS (raw_data, source_file)`
- `FROM (SELECT $1, METADATA$FILENAME FROM @RAW.S3_STAGE/raw/github/<ds>/repos.json)`
- JSON file format includes `STRIP_OUTER_ARRAY = TRUE` so a JSON array becomes 1 row per element.

## 7) dbt: How It Fits

dbt is the "T" in ELT:

- It is a SQL build tool + dependency graph.
- It turns your raw tables into modeled, documented analytics tables.

In this project:

- staging models are views that expose `raw_data` (simple but valid)
- marts model `fct_ingestion_counts` gives a clean final output proving the pipeline worked

## 8) Postgres: What It Was Used For

Postgres here is NOT part of the analytics pipeline.

It stores Airflow metadata:

- DAG runs
- task instance states
- scheduling info
- users/logins

Airflow needs a database for this, so Docker Compose runs a Postgres container.

## 9) Docker: Why It Matters Here

Docker gave us a reproducible environment:

- Everyone runs the same Airflow + Python deps
- Your laptop doesn't need to install Airflow/dbt globally
- Services (webserver, scheduler, postgres) run together as one stack

The key Docker concepts in this project:

- `Dockerfile.airflow` builds an **image** (a packaged filesystem + dependencies)
- Docker Compose runs **containers** (running processes from that image)
- Volumes mount your code into the container so you can edit locally and Airflow sees changes

## 10) How to Run / Control Everything (Commands)

Start the stack:

```bash
docker compose up -d --build
```

See running containers:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs --tail 200 airflow-webserver
docker compose logs --tail 200 airflow-scheduler
```

Run dbt inside Docker:

```bash
docker compose exec airflow-webserver bash -lc "cd /opt/airflow/dbt_project && dbt run"
```

Stop everything:

```bash
docker compose down
```

## 11) Common Beginner Confusions (and the Fix)

- "Where is the data stored?"
  - Raw files: S3
  - Raw tables + analytics models: Snowflake
  - Airflow metadata: Postgres

- "Why did counts double?"
  - Because `COPY INTO` appends when you re-run the same run date
  - In production you'd make loads idempotent (delete-by-source_file, MERGE, or file-tracking)

- "Why did Airflow Logs show 403 / connection errors?"
  - Served logs require consistent `AIRFLOW__WEBSERVER__SECRET_KEY`
  - Served logs also require stable hostnames so the webserver can resolve the scheduler

