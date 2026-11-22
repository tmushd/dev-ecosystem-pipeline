from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from analytics.tableau_dashboard import (
    DATA_FILE_NAME,
    PACKAGE_NAME,
    WORKBOOK_NAME,
    build_tableau_package,
)


def test_tableau_package_embeds_data_and_dashboard(tmp_path: Path) -> None:
    csv_path = tmp_path / DATA_FILE_NAME
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "repo_id",
                "repo_full_name",
                "stars",
                "forks",
                "days_since_last_push",
                "evaluation_score",
                "maintenance_risk",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "repo_id": 1,
                "repo_full_name": "example/active-project",
                "stars": 1000,
                "forks": 200,
                "days_since_last_push": 3,
                "evaluation_score": 87.5,
                "maintenance_risk": "ACTIVE",
            }
        )

    workbook_path = tmp_path / WORKBOOK_NAME
    package_path = tmp_path / PACKAGE_NAME
    build_tableau_package(csv_path, workbook_path, package_path)

    assert workbook_path.exists()
    with zipfile.ZipFile(package_path) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == {WORKBOOK_NAME, f"Data/{DATA_FILE_NAME}"}
        root = ElementTree.fromstring(package.read(WORKBOOK_NAME))

    assert root.find("./dashboards/dashboard[@name='Executive Overview']") is not None
    assert {sheet.get("name") for sheet in root.findall("./worksheets/worksheet")} == {
        "Repository Landscape",
        "Evaluation Ranking",
        "Maintenance Risk",
    }
    connection = root.find(".//connection[@class='textscan']")
    assert connection is not None
    assert connection.get("directory") == "Data"
    assert connection.get("filename") == DATA_FILE_NAME


def test_tableau_workbook_is_deterministic(tmp_path: Path) -> None:
    source = Path("outputs/analytics") / DATA_FILE_NAME
    first = tmp_path / "first.twb"
    second = tmp_path / "second.twb"
    build_tableau_package(source, first, tmp_path / "first.twbx")
    build_tableau_package(source, second, tmp_path / "second.twbx")
    assert first.read_bytes() == second.read_bytes()
    assert (tmp_path / "first.twbx").read_bytes() == (tmp_path / "second.twbx").read_bytes()
