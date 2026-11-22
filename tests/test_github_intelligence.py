from __future__ import annotations

import pandas as pd
import pytest

from analytics.github_intelligence import (
    analyze_maintenance_hypothesis,
    build_repo_daily,
    normalize_repository,
    stable_snapshot_key,
    upsert_snapshot,
    validate_snapshot,
)


def _repo(repo_id: int, stars: int = 100, pushed_at: str = "2026-11-15T00:00:00Z") -> dict:
    return {
        "id": repo_id,
        "full_name": f"owner/repo-{repo_id}",
        "name": f"repo-{repo_id}",
        "owner": {"login": "owner"},
        "stargazers_count": stars,
        "forks_count": 10,
        "open_issues_count": 2,
        "created_at": "2020-01-01T00:00:00Z",
        "pushed_at": pushed_at,
        "archived": False,
    }


def _frame(count: int = 8) -> pd.DataFrame:
    rows = [
        normalize_repository(_repo(i, stars=i * 100), snapshot_date="2026-11-21", run_id="test", source_file="fixture.json")
        for i in range(1, count + 1)
    ]
    return pd.DataFrame(rows)


def test_snapshot_key_is_deterministic() -> None:
    assert stable_snapshot_key(1, "2026-11-21") == stable_snapshot_key(1, "2026-11-21")
    assert stable_snapshot_key(1, "2026-11-21") != stable_snapshot_key(2, "2026-11-21")


def test_three_replays_are_idempotent() -> None:
    incoming = _frame()
    result = pd.DataFrame()
    for _ in range(3):
        result = upsert_snapshot(result, incoming)
    assert len(result) == len(incoming)
    assert not result.duplicated(["repo_id", "snapshot_date"]).any()


def test_quality_checks_pass_clean_data() -> None:
    checks = validate_snapshot(_frame())
    assert set(checks["status"]) == {"PASS"}


def test_quality_checks_reject_duplicate_and_negative_values() -> None:
    frame = _frame()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.loc[0, "stars"] = -1
    checks = validate_snapshot(frame).set_index("check_name")
    assert checks.loc["unique_repo_snapshot", "status"] == "FAIL"
    assert checks.loc["nonnegative_stars", "status"] == "FAIL"


def test_maintenance_hypothesis_reports_effect_and_uncertainty() -> None:
    daily = build_repo_daily(_frame())
    result = analyze_maintenance_hypothesis(daily)
    assert "absolute_rate_difference" in result
    assert "wilson_95_ci" in result["high_star"]
    assert result["high_star"]["n"] > 0


def test_missing_required_id_raises_during_normalization() -> None:
    repo = _repo(1)
    del repo["id"]
    with pytest.raises(KeyError):
        normalize_repository(repo, snapshot_date="2026-11-21", run_id="test", source_file="fixture.json")


def test_missing_issue_count_is_not_converted_to_zero() -> None:
    repo = _repo(1)
    repo["open_issues_count"] = None
    repo["open_issues_collection_status"] = "http_503"
    normalized = normalize_repository(repo, snapshot_date="2026-11-21", run_id="test", source_file="fixture.json")
    assert normalized["open_issues"] is None
    assert normalized["open_issues_collection_status"] == "http_503"
