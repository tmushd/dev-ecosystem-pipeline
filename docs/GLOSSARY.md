# Glossary (Key Terms)

## Pipeline Terms

- **ETL**: Extract -> Transform -> Load. Transform happens before loading into the warehouse.
- **ELT**: Extract -> Load -> Transform. Transform happens inside the warehouse (this project).
- **Orchestration**: Coordinating tasks, dependencies, retries, schedules, and monitoring (Airflow).
- **Idempotent**: If you run it twice with the same inputs, you get the same final state (no duplicates).

## Docker Terms

- **Docker image**: A packaged filesystem + dependencies (built from a Dockerfile). Think "blueprint".
- **Docker container**: A running instance of an image. Think "a process with an isolated filesystem".
- **Dockerfile**: Instructions to build an image (base image + install steps).
- **Docker Compose**: A YAML file that defines multiple containers that run together as one app stack.
- **Volume mount**: Mapping a folder from your laptop into the container so the container sees your code.
- **Port mapping**: Exposing a container port to your laptop (example: `8080:8080` for Airflow UI).

## Airflow Terms

- **DAG**: Directed Acyclic Graph. A set of tasks + dependencies (the workflow).
- **Task**: One step in a DAG (extract, load, dbt run, etc.).
- **Operator**: The "type" of task (PythonOperator runs Python; BashOperator runs shell).
- **Scheduler**: The Airflow component that decides what to run and runs tasks (in this project).
- **Webserver**: The Airflow UI.
- **`{{ ds }}`**: A templated string that becomes the run date (`YYYY-MM-DD`) for that run.

## AWS / S3 Terms

- **S3 bucket**: A top-level container for objects (files).
- **S3 object**: A file stored in S3 (data + metadata).
- **S3 key**: The full path/name of an object inside a bucket (example: `raw/github/2026-04-02/repos.json`).
- **Prefix**: A "folder-like" part of the key; S3 doesn't have real folders, just key prefixes.
- **IAM user**: An identity with access keys; used here to give the pipeline permission to write to S3.

## Snowflake Terms

- **Warehouse**: Snowflake compute resources; you pay while it runs queries.
- **Database / Schema**: Namespaces for tables (we used `DEV_ECOSYSTEM.RAW` and `DEV_ECOSYSTEM.ANALYTICS`).
- **Stage**: A Snowflake object that points to external files (S3) so Snowflake can load them.
- **`COPY INTO`**: Snowflake command to load data from files into a table.
- **`VARIANT`**: Snowflake data type for semi-structured data (JSON).
- **`METADATA$FILENAME`**: A Snowflake pseudo-column that returns the source file path during loading.

## dbt Terms

- **Model**: A SQL file that dbt runs to create a view/table in the warehouse.
- **Source**: A "raw table" input declared in YAML (so models can reference it safely).
- **`ref()`**: dbt function to reference another model (builds the dependency graph).
- **Materialization**: What dbt builds (`view`, `table`, `incremental`, etc.).

