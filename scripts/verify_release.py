from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((ROOT / "outputs/reports/latest_run_manifest.json").read_text())
    dq = pd.read_csv(ROOT / "outputs/reports/data_quality_results.csv")
    assert manifest["source_records"] >= 30, "portfolio evidence must contain at least 30 live repositories"
    assert manifest["idempotency_replays"] == 3
    assert len(set(manifest["row_count_after_each_replay"])) == 1
    assert manifest["duplicate_snapshot_keys"] == 0
    assert len(manifest["source_sha256"]) == 64
    assert (dq["status"] == "PASS").all()
    mart = pd.read_csv(ROOT / "outputs/analytics/mart_repo_momentum.csv")
    assert (mart["open_issues"] > 0).any(), "evidence must include observable issue counts"
    unavailable = mart["open_issues_collection_status"] != "observed"
    assert mart.loc[unavailable, "open_issues"].isna().all(), "unavailable issue counts must remain null"
    assert manifest["missing_issue_counts_preserved_as_null"] == int(mart["open_issues"].isna().sum())
    assert (ROOT / "outputs/dashboard/ecosystem_intelligence_dashboard.html").stat().st_size > 10_000
    print("Release gates passed:", json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
