from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

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
    package_path = ROOT / "outputs/dashboard/Open_Source_Ecosystem_Intelligence.twbx"
    assert package_path.stat().st_size > 10_000
    assert manifest["tableau_package"] == "outputs/dashboard/Open_Source_Ecosystem_Intelligence.twbx"
    assert len(manifest["tableau_package_sha256"]) == 64
    assert hashlib.sha256(package_path.read_bytes()).hexdigest() == manifest["tableau_package_sha256"]
    assert manifest["tableau_embedded_rows"] == len(mart)
    assert manifest["tableau_dashboard"] == "Executive Overview"
    with zipfile.ZipFile(package_path) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == {
            "Open_Source_Ecosystem_Intelligence.twb",
            "Data/tableau_repo_momentum_extract.csv",
        }
        workbook = ElementTree.fromstring(package.read("Open_Source_Ecosystem_Intelligence.twb"))
        assert [sheet.get("name") for sheet in workbook.findall("./worksheets/worksheet")] == [
            "Repository Landscape",
            "Evaluation Ranking",
            "Maintenance Risk",
        ]
        assert workbook.find("./dashboards/dashboard[@name='Executive Overview']") is not None
    print("Release gates passed:", json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
