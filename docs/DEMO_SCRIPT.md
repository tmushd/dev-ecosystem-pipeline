# Demo Script (60 to 90 seconds)

If a recruiter asks "what did you build?", this is a simple walkthrough.

## 1) One sentence

I built an end-to-end ELT pipeline that extracts live API data, lands raw JSON in S3 by run date, loads it into Snowflake with `COPY INTO`, and uses dbt to model an analytics-ready table, all orchestrated by Airflow.

## 2) Show the orchestration

- Open Airflow -> DAG `dev_ecosystem_elt`
- Point out parallel tasks (GitHub, CoinGecko, Hacker News) -> single load -> dbt

## 3) Show the data lake landing zone

- Open S3 -> show date-partitioned objects under `raw/<source>/YYYY-MM-DD/`

## 4) Show the warehouse + transformations

In Snowflake:

```sql
select * from dev_ecosystem.analytics.fct_ingestion_counts order by source_name;
```

Explain:

- RAW tables store JSON in `VARIANT` plus `source_file` for lineage
- dbt creates staging views + a mart table

## 5) One "production" note

This pipeline uses a realistic ingestion pattern: object storage landing -> warehouse `COPY INTO` instead of loading from local files.

