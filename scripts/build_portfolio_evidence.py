from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

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

    hypothesis_a = analyze_maintenance_hypothesis(daily)
    hypothesis_b = assess_growth_hypothesis_readiness(daily)
    write_json({"hypothesis_a": hypothesis_a, "hypothesis_b": hypothesis_b}, reports / "hypothesis_results.json")

    analytics_figure = px.scatter(
        latest,
        x="stars",
        y="days_since_last_push",
        size="forks",
        color="maintenance_risk",
        hover_name="repo_full_name",
        log_x=True,
        title="Open-Source Data Engineering: Popularity vs. Maintenance Recency",
        labels={"stars": "GitHub stars (log scale)", "days_since_last_push": "Days since latest commit"},
    )
    reliability_figure = go.Figure()
    indicators = [
        ("Current snapshot rows", len(latest), [0.0, 0.48], [0.52, 1.0]),
        ("Quality checks passed", int((dq["status"] == "PASS").sum()), [0.52, 1.0], [0.52, 1.0]),
        ("Replay row-count variance", max(len(once), len(twice), len(thrice)) - min(len(once), len(twice), len(thrice)), [0.0, 0.48], [0.0, 0.46]),
        ("Duplicate snapshot keys", int(thrice.duplicated(["repo_id", "snapshot_date"]).sum()), [0.52, 1.0], [0.0, 0.46]),
    ]
    for title, value, x_domain, y_domain in indicators:
        reliability_figure.add_trace(
            go.Indicator(mode="number", value=value, title={"text": title}, domain={"x": x_domain, "y": y_domain})
        )
    reliability_figure.update_layout(title=f"Data Reliability — latest successful snapshot {args.snapshot_date}", height=420)

    dashboard_dir = ROOT / "outputs" / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    dashboard_html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Open-Source Ecosystem Intelligence</title></head>
<body style='font-family:Arial,sans-serif;margin:24px'><h1>Open-Source Ecosystem Intelligence</h1>
<p>Decision-support dashboard generated from the governed repository-day fact table.</p>
{pio.to_html(reliability_figure, full_html=False, include_plotlyjs='cdn')}
<h2>Ecosystem analytics</h2>{pio.to_html(analytics_figure, full_html=False, include_plotlyjs=False)}
</body></html>"""
    (dashboard_dir / "ecosystem_intelligence_dashboard.html").write_text(dashboard_html, encoding="utf-8")

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
