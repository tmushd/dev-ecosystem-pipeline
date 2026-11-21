import pytest

from scripts.load_to_snowflake import _merge_sql, _stage_sql


def test_stage_uses_storage_integration_not_embedded_keys() -> None:
    sql = _stage_sql("example-bucket", "DEV_ECOSYSTEM_S3_INT")
    assert "STORAGE_INTEGRATION" in sql
    assert "AWS_SECRET_KEY" not in sql


def test_invalid_storage_integration_identifier_is_rejected() -> None:
    with pytest.raises(ValueError):
        _stage_sql("example-bucket", "unsafe; drop stage")


def test_merge_is_keyed_for_idempotency() -> None:
    sql = _merge_sql(
        table="RAW.RAW_GITHUB_REPOS",
        stage_path="RAW.S3_STAGE/raw/github/2026-11-21/repos.json",
        run_date="2026-11-21",
        run_id="test-run",
        id_expression="$1:id::STRING",
    )
    assert "MERGE INTO" in sql
    assert "target.snapshot_key = source.snapshot_key" in sql
    assert "WHEN MATCHED" in sql and "WHEN NOT MATCHED" in sql
