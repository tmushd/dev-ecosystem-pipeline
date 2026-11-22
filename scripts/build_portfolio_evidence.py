from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.github_intelligence import (  # noqa: E402
    SNAPSHOT_COLUMNS,
    analyze_maintenance_hypothesis,
    assess_growth_hypothesis_readiness,
    build_momentum_mart,
    build_repo_daily,
    collect_public_github_snapshot,
    new_run_id,
    normalize_repository,
    upsert_snapshot,
    validate_snapshot,
    write_json,
)
from analytics.tableau_dashboard import build_tableau_package, default_paths  # noqa: E402


def main() -> None:
    started_clock = time.perf_counter()
    started_at = datetime.now(timezone.utc)
    parser = argparse.ArgumentParser(description="Build reproducible local analytics evidence from public GitHub data.")
    parser.add_argument("--snapshot-date", default=date.today().isoformat())
    parser.add_argument("--pages", type=int, default=5, help="Ten GitHub repositories per search page")
    args = parser.parse_args()

    run_id = new_run_id(args.snapshot_date)
    raw_records = collect_public_github_snapshot(pages=args.pages, snapshot_date=args.snapshot_date)
    raw_path = ROOT / "data" / "raw" / "github" / args.snapshot_date / "repos.json"
    write_json(raw_records, raw_path)

    normalized = pd.DataFrame(
        [
            normalize_repository(
                record,
                snapshot_date=args.snapshot_date,
                run_id=run_id,
                source_file=str(raw_path.relative_to(ROOT)),
            )
            for record in raw_records
        ],
        columns=SNAPSHOT_COLUMNS,
    )
    snapshot_path = ROOT / "data" / "curated" / "github_repo_snapshots.parquet"
    existing = pd.read_parquet(snapshot_path) if snapshot_path.exists() else pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    once = upsert_snapshot(existing, normalized)
    twice = upsert_snapshot(once, normalized)
    thrice = upsert_snapshot(twice, normalized)
    if len(once) != len(thrice) or once[["repo_id", "snapshot_date"]].duplicated().any():
        raise RuntimeError("Idempotency acceptance test failed")

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    thrice.to_parquet(snapshot_path, index=False)
    thrice.to_csv(snapshot_path.with_suffix(".csv"), index=False)

    dq = validate_snapshot(thrice)
    if (dq["status"] == "FAIL").any():
        raise RuntimeError("Data quality gates failed:\n" + dq.to_string(index=False))
    reports = ROOT / "outputs" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    dq.to_csv(reports / "data_quality_results.csv", index=False)

    daily = build_repo_daily(thrice)
    mart = build_momentum_mart(daily)
    latest = mart[mart["snapshot_date"] == mart["snapshot_date"].max()].copy()
    analytics_dir = ROOT / "outputs" / "analytics"
    analytics_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(analytics_dir / "fct_repo_daily.parquet", index=False)
    latest.to_csv(analytics_dir / "mart_repo_momentum.csv", index=False)
    latest.to_csv(analytics_dir / "tableau_repo_momentum_extract.csv", index=False)

    csv_path, workbook_path, package_path = default_paths(ROOT)
    build_tableau_package(csv_path, workbook_path, package_path)

    hypothesis_a = analyze_maintenance_hypothesis(daily)
    hypothesis_b = assess_growth_hypothesis_readiness(daily)
    write_json({"hypothesis_a": hypothesis_a, "hypothesis_b": hypothesis_b}, reports / "hypothesis_results.json")

    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "run_id": run_id,
        "status": "SUCCESS",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.perf_counter() - started_clock, 3),
        "snapshot_date": args.snapshot_date,
        "source_query": "topic:data-engineering language:Python sort:stars-desc",
        "source_file": str(raw_path.relative_to(ROOT)),
        "source_sha256": sha256(raw_path),
        "source_records": len(raw_records),
        "curated_rows": len(thrice),
        "current_snapshot_rows": len(latest),
        "idempotency_replays": 3,
        "row_count_after_each_replay": [len(once), len(twice), len(thrice)],
        "duplicate_snapshot_keys": int(thrice.duplicated(["repo_id", "snapshot_date"]).sum()),
        "quality_checks_passed": int((dq["status"] == "PASS").sum()),
        "quality_checks_total": len(dq),
        "tableau_package": str(package_path.relative_to(ROOT)),
        "tableau_package_sha256": sha256(package_path),
        "tableau_embedded_rows": len(latest),
        "tableau_worksheets": ["Repository Landscape", "Evaluation Ranking", "Maintenance Risk"],
        "tableau_dashboard": "Executive Overview",
        "open_issue_counts_observed": int(latest["open_issues"].notna().sum()),
        "open_issue_count_coverage": float(latest["open_issues"].notna().mean()),
        "missing_issue_counts_preserved_as_null": int(latest["open_issues"].isna().sum()),
        "hypothesis_a": hypothesis_a,
        "hypothesis_b": hypothesis_b,
    }
    write_json(manifest, reports / "latest_run_manifest.json")
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    main()
