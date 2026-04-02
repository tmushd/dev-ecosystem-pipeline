# Interview Prep

This is a short set of questions you can expect and the key points to hit.

## Architecture and Design

**Q: What problem does S3 solve here? Why not load straight into Snowflake?**

- S3 provides a durable landing zone for raw data.
- You can replay loads without re-hitting APIs.
- `COPY INTO` from an external stage is a common production ingestion pattern.

**Q: Why store JSON as `VARIANT` in RAW instead of flattening immediately?**

- Keeps the pipeline resilient to schema changes in APIs.
- Lets dbt handle normalization and business modeling in the analytics layer.

**Q: How do you handle schema drift?**

- RAW stores JSON as `VARIANT`.
- dbt staging models select only needed fields and can evolve safely.

## Orchestration (Airflow)

**Q: What does the DAG do?**

- Runs API extracts in parallel.
- Uploads raw JSON to S3 by run date.
- Loads into Snowflake using `COPY INTO`.
- Runs dbt staging then marts.

**Q: How would you add retries/backoff?**

- Use retry logic in extractors (HTTP 429/5xx) and Airflow retries at the task level.

## Snowflake Ingestion

**Q: How does Snowflake load from S3?**

- External stage points to `s3://<bucket>`.
- `COPY INTO` loads JSON into `VARIANT`.
- `METADATA$FILENAME` is stored in `source_file` for lineage and debugging.

**Q: How do you prevent duplicates?**

- Production options:
  - Load into a temp table then `MERGE` by a natural key.
  - Delete by `source_file` for a run date before re-loading.
  - Use Snowpipe / event-based ingestion with idempotent design.

## dbt

**Q: What is the difference between staging and marts?**

- Staging: light cleaning/standardization, closer to source.
- Marts: business-facing tables for reporting/analytics.

**Q: What did dbt build here?**

- Staging views per source.
- A mart table `ANALYTICS.fct_ingestion_counts` that summarizes row counts per source.

## Practical Talking Points

- Mention date partitioning in S3 (`YYYY-MM-DD`) and why it's helpful.
- Mention observability: logs show S3 keys + `COPY INTO` statements.
- Mention security: credentials come from env vars, no hardcoding.

