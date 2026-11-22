from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass

import snowflake.connector
from dotenv import load_dotenv


@dataclass(frozen=True)
class LoadResult:
    source_name: str
    target_table: str
    stage_path: str
    affected_rows: int


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _snowflake_connection():
    return snowflake.connector.connect(
        account=_required_env("SNOWFLAKE_ACCOUNT"),
        user=_required_env("SNOWFLAKE_USER"),
        password=_required_env("SNOWFLAKE_PASSWORD"),
        warehouse=_required_env("SNOWFLAKE_WAREHOUSE"),
        database=_required_env("SNOWFLAKE_DATABASE"),
        role=os.getenv("SNOWFLAKE_ROLE") or None,
    )


def _stage_sql(bucket: str, storage_integration: str) -> str:
    """Create a credential-free external stage backed by a Snowflake integration."""
    safe_bucket = bucket.replace("'", "''")
    if not storage_integration.replace("_", "").isalnum():
        raise ValueError("SNOWFLAKE_STORAGE_INTEGRATION must be an unquoted identifier")
    return f"""
CREATE STAGE IF NOT EXISTS RAW.S3_STAGE
  URL = 's3://{safe_bucket}'
  STORAGE_INTEGRATION = {storage_integration}
  FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = TRUE);
""".strip()


def _ensure_raw_objects(cur) -> None:
    cur.execute("CREATE SCHEMA IF NOT EXISTS RAW")
    for table in [
        "RAW_GITHUB_REPOS",
        "RAW_COINGECKO_MARKETS",
        "RAW_COINGECKO_PRICE_HISTORY",
        "RAW_HACKERNEWS_POSTS",
    ]:
        cur.execute(
            f"""
CREATE TABLE IF NOT EXISTS RAW.{table} (
  snapshot_key STRING NOT NULL,
  source_record_id STRING NOT NULL,
  snapshot_date DATE NOT NULL,
  raw_data VARIANT NOT NULL,
  source_file STRING NOT NULL,
  run_id STRING NOT NULL,
  ingested_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT uq_{table.lower()} UNIQUE (snapshot_key)
)
""".strip()
        )
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS RAW.PIPELINE_RUN_AUDIT (
  run_id STRING,
  snapshot_date DATE,
  source_name STRING,
  target_table STRING,
  affected_rows NUMBER,
  loaded_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP(),
  status STRING
)
""".strip()
    )
    cur.execute(
        "CREATE OR REPLACE VIEW RAW.VW_REDDIT_POSTS_LEGACY AS "
        "SELECT raw_data, source_file, ingested_at FROM RAW.RAW_HACKERNEWS_POSTS"
    )


def _merge_sql(*, table: str, stage_path: str, run_date: str, run_id: str, id_expression: str) -> str:
    """Build a replay-safe merge. All interpolated identifiers/paths are controlled by the caller."""
    return f"""
MERGE INTO {table} AS target
USING (
  SELECT
    SHA2(CONCAT('{table}|', {id_expression}, '|', '{run_date}'), 256) AS snapshot_key,
    {id_expression} AS source_record_id,
    TO_DATE('{run_date}') AS snapshot_date,
    $1 AS raw_data,
    METADATA$FILENAME AS source_file,
    COALESCE($1:_ingestion_metadata:run_id::STRING, '{run_id}') AS run_id,
    CURRENT_TIMESTAMP() AS ingested_at
  FROM @{stage_path}
) AS source
ON target.snapshot_key = source.snapshot_key
WHEN MATCHED THEN UPDATE SET
  raw_data = source.raw_data,
  source_file = source.source_file,
  run_id = source.run_id,
  ingested_at = source.ingested_at
WHEN NOT MATCHED THEN INSERT
  (snapshot_key, source_record_id, snapshot_date, raw_data, source_file, run_id, ingested_at)
VALUES
  (source.snapshot_key, source.source_record_id, source.snapshot_date, source.raw_data, source.source_file, source.run_id, source.ingested_at)
""".strip()


def load_run_date(*, run_date: str, run_id: str | None = None) -> Iterable[LoadResult]:
    """Merge one S3 partition into Snowflake atomically and idempotently."""
    load_dotenv()
    bucket = _required_env("S3_BUCKET_NAME")
    integration = _required_env("SNOWFLAKE_STORAGE_INTEGRATION")
    run_id = run_id or f"manual-{run_date}"
    tasks = [
        ("github", "RAW.RAW_GITHUB_REPOS", f"RAW.S3_STAGE/raw/github/{run_date}/repos.json", "$1:id::STRING"),
        ("coingecko_markets", "RAW.RAW_COINGECKO_MARKETS", f"RAW.S3_STAGE/raw/coingecko/{run_date}/markets.json", "$1:id::STRING"),
        (
            "coingecko_price_history",
            "RAW.RAW_COINGECKO_PRICE_HISTORY",
            f"RAW.S3_STAGE/raw/coingecko/{run_date}/price_history.json",
            "$1:coin_id::STRING",
        ),
        ("hackernews", "RAW.RAW_HACKERNEWS_POSTS", f"RAW.S3_STAGE/raw/hackernews/{run_date}/posts.json", "$1:id::STRING"),
    ]

    with _snowflake_connection() as conn:
        conn.autocommit(False)
        try:
            with conn.cursor() as cur:
                _ensure_raw_objects(cur)
                cur.execute(_stage_sql(bucket, integration))
                results = []
                for source_name, table, stage_path, id_expression in tasks:
                    logging.info("MERGE %s from @%s", table, stage_path)
                    cur.execute(
                        _merge_sql(
                            table=table,
                            stage_path=stage_path,
                            run_date=run_date,
                            run_id=run_id,
                            id_expression=id_expression,
                        )
                    )
                    affected = max(cur.rowcount or 0, 0)
                    cur.execute(
                        "INSERT INTO RAW.PIPELINE_RUN_AUDIT "
                        "(run_id, snapshot_date, source_name, target_table, affected_rows, status) "
                        "VALUES (%s, %s, %s, %s, %s, 'SUCCESS')",
                        (run_id, run_date, source_name, table, affected),
                    )
                    results.append(LoadResult(source_name, table, stage_path, affected))
            conn.commit()
            yield from results
        except Exception:
            conn.rollback()
            logging.exception("Warehouse load rolled back for run_id=%s date=%s", run_id, run_date)
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    selected_date = os.getenv("RUN_DATE")
    if not selected_date:
        raise SystemExit("Set RUN_DATE=YYYY-MM-DD to run this script directly.")
    list(load_run_date(run_date=selected_date, run_id=os.getenv("PIPELINE_RUN_ID")))
