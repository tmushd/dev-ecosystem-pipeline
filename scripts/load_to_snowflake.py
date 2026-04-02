import logging
import os
from typing import Iterable, Tuple

import snowflake.connector
from dotenv import load_dotenv


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _snowflake_connection():
    account = _required_env("SNOWFLAKE_ACCOUNT")
    user = _required_env("SNOWFLAKE_USER")
    password = _required_env("SNOWFLAKE_PASSWORD")
    warehouse = _required_env("SNOWFLAKE_WAREHOUSE")
    database = _required_env("SNOWFLAKE_DATABASE")

    return snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
    )


def _stage_sql(bucket: str, aws_key_id: str, aws_secret_key: str) -> str:
    # Use a stage-scoped JSON file format that can load JSON arrays into one row per element.
    def _esc(value: str) -> str:
        return value.replace("'", "''")

    return f"""
CREATE OR REPLACE STAGE RAW.S3_STAGE
  URL = 's3://{_esc(bucket)}'
  CREDENTIALS = (AWS_KEY_ID='{_esc(aws_key_id)}' AWS_SECRET_KEY='{_esc(aws_secret_key)}')
  FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = TRUE);
""".strip()


def _ensure_raw_objects(cur) -> None:
    cur.execute("CREATE SCHEMA IF NOT EXISTS RAW;")

    cur.execute(
        """
CREATE TABLE IF NOT EXISTS RAW.RAW_GITHUB_REPOS (
  raw_data VARIANT,
  source_file STRING,
  ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
""".strip()
    )

    cur.execute(
        """
CREATE TABLE IF NOT EXISTS RAW.RAW_COINGECKO_MARKETS (
  raw_data VARIANT,
  source_file STRING,
  ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
""".strip()
    )

    cur.execute(
        """
CREATE TABLE IF NOT EXISTS RAW.RAW_COINGECKO_PRICE_HISTORY (
  raw_data VARIANT,
  source_file STRING,
  ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
""".strip()
    )

    cur.execute(
        """
CREATE TABLE IF NOT EXISTS RAW.RAW_REDDIT_POSTS (
  raw_data VARIANT,
  source_file STRING,
  ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
""".strip()
    )


def _copy_into(cur, *, table: str, stage_path: str) -> None:
    # Load each JSON element into raw_data; preserve the filename for traceability.
    sql = f"""
COPY INTO {table} (raw_data, source_file)
FROM (
  SELECT $1, METADATA$FILENAME
  FROM @{stage_path}
)
FILE_FORMAT = (TYPE = JSON STRIP_OUTER_ARRAY = TRUE)
ON_ERROR = 'CONTINUE';
""".strip()
    cur.execute(sql)


def load_run_date(*, run_date: str) -> Iterable[Tuple[str, str]]:
    """
    Load raw JSON files from S3 into Snowflake RAW schema using COPY INTO.

    Uses S3 keys:
    - raw/github/{run_date}/repos.json
    - raw/coingecko/{run_date}/markets.json
    - raw/coingecko/{run_date}/price_history.json
    - raw/hackernews/{run_date}/posts.json
    """
    # Makes local runs work with a `.env` file; in Airflow, env vars are already injected.
    load_dotenv()

    bucket = _required_env("S3_BUCKET_NAME")
    aws_key_id = _required_env("AWS_ACCESS_KEY_ID")
    aws_secret_key = _required_env("AWS_SECRET_ACCESS_KEY")

    tasks = [
        ("RAW.RAW_GITHUB_REPOS", f"RAW.S3_STAGE/raw/github/{run_date}/repos.json"),
        ("RAW.RAW_COINGECKO_MARKETS", f"RAW.S3_STAGE/raw/coingecko/{run_date}/markets.json"),
        (
            "RAW.RAW_COINGECKO_PRICE_HISTORY",
            f"RAW.S3_STAGE/raw/coingecko/{run_date}/price_history.json",
        ),
        # Keep the existing RAW table name so dbt models remain unchanged.
        ("RAW.RAW_REDDIT_POSTS", f"RAW.S3_STAGE/raw/hackernews/{run_date}/posts.json"),
    ]

    with _snowflake_connection() as conn:
        with conn.cursor() as cur:
            logging.info("Ensuring Snowflake RAW schema, tables, and stage exist")
            _ensure_raw_objects(cur)
            cur.execute(_stage_sql(bucket, aws_key_id, aws_secret_key))

            for table, stage_path in tasks:
                logging.info("COPY INTO %s from @%s", table, stage_path)
                _copy_into(cur, table=table, stage_path=stage_path)
                yield (table, stage_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    run_date = os.getenv("RUN_DATE")
    if not run_date:
        raise SystemExit("Set RUN_DATE=YYYY-MM-DD to run this script directly.")
    list(load_run_date(run_date=run_date))
