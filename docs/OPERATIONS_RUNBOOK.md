# Operations runbook

## Release gates

Run `make verify`. A healthy local release requires all unit tests and lint checks, at least 30 live repository records, three replay counts that are identical, zero duplicate snapshot keys, all DQ checks passing, and a generated dashboard over 10 KB.

For cloud runs, execute `dbt source freshness` followed by `dbt build`. Any freshness error, singular-test row, or schema-test failure blocks the mart.

## Incident response

### GitHub extraction failure

Inspect HTTP status and rate-limit headers. Transient 429/5xx responses retry six times with exponential backoff. Authentication, query, or schema errors must fail visibly; do not publish a partial GitHub partition as complete.

### S3 or Snowflake load failure

The loader wraps all source merges and audit writes in one transaction. Confirm the storage integration, stage path, and S3 object. The transaction rolls back on failure, so rerun the same `run_id` and date after correction.

### Duplicate-key failure

Compare `repo_id`, `snapshot_date`, `source_file`, and `run_id`. The raw merge key is deterministic. A duplicate in dbt indicates a key policy or source identity regression, not a record to silently drop.

### Reconciliation failure

Compare staging and fact counts by snapshot date. Check rejected casts and the incremental watermark. Backfill the affected date into a staging target, run all tests, and promote only after counts match.

### Stale source

Warnings begin after 36 hours and errors after 72. Confirm the Airflow run and S3 partition before re-running. Do not reset freshness timestamps manually.

## Backfill

Trigger the DAG with the desired logical date and a unique run ID. S3 keys are date-partitioned; Snowflake merge keys make the operation replay safe. Run `dbt build --full-refresh` only when model logic changes, not for ordinary late data.

## Cost controls

Use an X-Small auto-suspending warehouse, one active Airflow run, bounded GitHub pagination, and date-scoped merges. The local evidence path is appropriate for review and CI; it does not require cloud resources.
