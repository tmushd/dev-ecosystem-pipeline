from pathlib import Path


def test_dbt_freshness_precedes_dependency_aware_build() -> None:
    dag_source = (Path(__file__).resolve().parents[1] / "dags/ecosystem_elt_dag.py").read_text()
    assert "dbt source freshness" in dag_source
    assert "dbt build" in dag_source
    dependency = "load_to_snowflake >> dbt_source_freshness >> dbt_build"
    assert dependency in dag_source
    assert "dbt_run_staging >> dbt_test >> dbt_run_marts" not in dag_source
