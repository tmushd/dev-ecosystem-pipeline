import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from extractors.coingecko_extractor import extract_coingecko
from extractors.github_extractor import extract_github_repos
from extractors.hackernews_extractor import extract_hackernews_posts


def _log_s3_landing_zone(run_date: str) -> None:
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    if bucket and region:
        logging.info("Landing raw API JSON in S3 bucket=%s region=%s run_date=%s", bucket, region, run_date)
    else:
        logging.info("Landing raw API JSON in S3 run_date=%s (bucket/region will be read from env at runtime)", run_date)


def _load_to_snowflake(run_date: str, run_id: str) -> None:
    # scripts/ isn't on the default Airflow import path, so add it at runtime.
    dags_dir = os.path.dirname(__file__)
    scripts_dir = os.path.normpath(os.path.join(dags_dir, "..", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    from load_to_snowflake import load_run_date  # noqa: WPS433 (runtime import)

    _log_s3_landing_zone(run_date)
    list(load_run_date(run_date=run_date, run_id=run_id))


with DAG(
    dag_id="dev_ecosystem_elt",
    start_date=datetime(2025, 1, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-platform",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=45),
    },
    tags=["portfolio", "api", "s3", "snowflake", "dbt"],
) as dag:
    extract_github = PythonOperator(
        task_id="extract_github",
        python_callable=extract_github_repos,
        op_kwargs={"run_date": "{{ ds }}", "run_id": "{{ run_id }}"},
    )

    extract_coingecko_task = PythonOperator(
        task_id="extract_coingecko",
        python_callable=extract_coingecko,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    extract_hackernews = PythonOperator(
        task_id="extract_hackernews",
        python_callable=extract_hackernews_posts,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    load_to_snowflake = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=_load_to_snowflake,
        op_kwargs={"run_date": "{{ ds }}", "run_id": "{{ run_id }}"},
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command="cd /opt/airflow/dbt_project && dbt source freshness",
        env={"DBT_PROFILES_DIR": "/opt/airflow/dbt_project"},
        append_env=True,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /opt/airflow/dbt_project && dbt build",
        env={"DBT_PROFILES_DIR": "/opt/airflow/dbt_project"},
        append_env=True,
    )

    [extract_github, extract_coingecko_task, extract_hackernews] >> load_to_snowflake >> dbt_source_freshness >> dbt_build
