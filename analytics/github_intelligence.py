from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from scipy.stats import fisher_exact

USER_AGENT = "open-source-ecosystem-intelligence/2.0"
SNAPSHOT_COLUMNS = [
    "repo_id",
    "repo_full_name",
    "owner_login",
    "repo_name",
    "html_url",
    "description",
    "stars",
    "forks",
    "open_issues",
    "created_at",
    "last_push_at",
    "archived",
    "snapshot_date",
    "run_id",
    "ingested_at",
    "source_file",
]


@dataclass(frozen=True)
class QualityCheck:
    check_name: str
    status: str
    failed_rows: int
    details: str


def stable_snapshot_key(repo_id: int, snapshot_date: str) -> str:
    return hashlib.sha256(f"{repo_id}|{snapshot_date}".encode()).hexdigest()


def normalize_repository(
    repo: dict[str, Any], *, snapshot_date: str, run_id: str, source_file: str
) -> dict[str, Any]:
    owner = repo.get("owner") or {}
    return {
        "repo_id": int(repo["id"]),
        "repo_full_name": str(repo["full_name"]),
        "owner_login": str(owner.get("login") or repo["full_name"].split("/", 1)[0]),
        "repo_name": str(repo.get("name") or repo["full_name"].split("/", 1)[1]),
        "html_url": str(repo.get("html_url") or f"https://github.com/{repo['full_name']}"),
        "description": repo.get("description"),
        "stars": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "open_issues": int(repo.get("open_issues_count") or 0),
        "created_at": repo.get("created_at"),
        "last_push_at": repo.get("pushed_at") or repo.get("updated_at"),
        "archived": bool(repo.get("archived", False)),
        "snapshot_date": snapshot_date,
        "run_id": run_id,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
    }


def upsert_snapshot(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Idempotent partition merge on the declared repository/day grain."""
    combined = pd.concat([existing, incoming], ignore_index=True) if not existing.empty else incoming.copy()
    combined = combined.sort_values(["snapshot_date", "repo_id", "ingested_at"])
    combined = combined.drop_duplicates(["repo_id", "snapshot_date"], keep="last")
    return combined.sort_values(["snapshot_date", "repo_id"]).reset_index(drop=True)


def validate_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    checks: list[QualityCheck] = []

    def add(name: str, mask: pd.Series, details: str) -> None:
        failed = int(mask.fillna(True).sum())
        checks.append(QualityCheck(name, "PASS" if failed == 0 else "FAIL", failed, details))

    add("required_repo_id", frame["repo_id"].isna(), "repo_id must be populated")
    add("required_snapshot_date", frame["snapshot_date"].isna(), "snapshot_date must be populated")
    duplicate_mask = frame.duplicated(["repo_id", "snapshot_date"], keep=False)
    add("unique_repo_snapshot", duplicate_mask, "repo_id + snapshot_date is the declared grain")
    add("nonnegative_stars", frame["stars"] < 0, "stars must be nonnegative")
    add("nonnegative_forks", frame["forks"] < 0, "forks must be nonnegative")
    add("nonnegative_open_issues", frame["open_issues"] < 0, "open issues must be nonnegative")
    created = pd.to_datetime(frame["created_at"], utc=True, errors="coerce")
    pushed = pd.to_datetime(frame["last_push_at"], utc=True, errors="coerce")
    add("valid_timestamps", created.isna() | pushed.isna(), "created_at and last_push_at must parse")
    add("valid_date_order", pushed < created, "last_push_at cannot precede created_at")
    return pd.DataFrame(asdict(check) for check in checks)


def build_repo_daily(snapshot: pd.DataFrame) -> pd.DataFrame:
    result = snapshot.copy()
    snapshot_ts = pd.to_datetime(result["snapshot_date"], utc=True)
    pushed_ts = pd.to_datetime(result["last_push_at"], utc=True)
    created_ts = pd.to_datetime(result["created_at"], utc=True)
    result["days_since_last_push"] = (snapshot_ts - pushed_ts).dt.total_seconds().div(86400).clip(lower=0)
    result["repo_age_days"] = (snapshot_ts - created_ts).dt.total_seconds().div(86400).clip(lower=1)
    result["is_recently_maintained_30d"] = result["days_since_last_push"] <= 30
    result["fork_to_star_ratio"] = result["forks"] / result["stars"].replace(0, np.nan)
    result["issue_to_star_ratio"] = result["open_issues"] / result["stars"].replace(0, np.nan)
    result["snapshot_key"] = [
        stable_snapshot_key(repo_id, snapshot_date)
        for repo_id, snapshot_date in zip(result["repo_id"], result["snapshot_date"], strict=True)
    ]
    return result


def build_momentum_mart(repo_daily: pd.DataFrame) -> pd.DataFrame:
    result = repo_daily.sort_values(["repo_id", "snapshot_date"]).copy()
    result["star_growth"] = result.groupby("repo_id")["stars"].diff()
    result["fork_growth"] = result.groupby("repo_id")["forks"].diff()
    result["history_days"] = result.groupby("repo_id")["snapshot_date"].transform("nunique")
    star_score = result["stars"].rank(pct=True)
    fork_score = result["forks"].rank(pct=True)
    activity_score = np.exp(-result["days_since_last_push"] / 45).clip(0, 1)
    result["evaluation_score"] = (100 * (0.40 * activity_score + 0.35 * star_score + 0.25 * fork_score)).round(2)
    result["maintenance_risk"] = np.select(
        [result["days_since_last_push"] > 180, result["days_since_last_push"] > 90],
        ["HIGH", "WATCH"],
        default="ACTIVE",
    )
    result["growth_evidence_status"] = np.where(
        result["history_days"] >= 14, "READY_FOR_LONGITUDINAL_ANALYSIS", "COLLECTING_HISTORY"
    )
    return result.sort_values(["snapshot_date", "evaluation_score"], ascending=[False, False])


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (float("nan"), float("nan"))
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    return (float(center - margin), float(center + margin))


def analyze_maintenance_hypothesis(repo_daily: pd.DataFrame) -> dict[str, Any]:
    latest_date = repo_daily["snapshot_date"].max()
    latest = repo_daily.loc[repo_daily["snapshot_date"] == latest_date].copy()
    cutoff = float(latest["stars"].quantile(0.75))
    latest["star_group"] = np.where(latest["stars"] >= cutoff, "high_star_top_quartile", "lower_three_quartiles")
    high = latest[latest["star_group"] == "high_star_top_quartile"]
    low = latest[latest["star_group"] == "lower_three_quartiles"]
    high_active = int(high["is_recently_maintained_30d"].sum())
    low_active = int(low["is_recently_maintained_30d"].sum())
    odds_ratio, p_value = fisher_exact(
        [[high_active, len(high) - high_active], [low_active, len(low) - low_active]], alternative="two-sided"
    )
    high_rate = high_active / len(high) if len(high) else float("nan")
    low_rate = low_active / len(low) if len(low) else float("nan")
    return {
        "hypothesis": "Top-quartile starred repositories have a greater proportion of pushes within 30 days.",
        "snapshot_date": str(latest_date),
        "star_cutoff": cutoff,
        "high_star": {"n": len(high), "active": high_active, "rate": high_rate, "wilson_95_ci": _wilson_interval(high_active, len(high))},
        "lower_star": {"n": len(low), "active": low_active, "rate": low_rate, "wilson_95_ci": _wilson_interval(low_active, len(low))},
        "absolute_rate_difference": float(high_rate - low_rate),
        "odds_ratio": float(odds_ratio),
        "fisher_exact_p_value": float(p_value),
        "interpretation_guardrail": "Observational association only; repository age, organization size, and selection criteria may confound the result.",
    }


def assess_growth_hypothesis_readiness(repo_daily: pd.DataFrame, minimum_snapshots: int = 14) -> dict[str, Any]:
    snapshot_count = int(repo_daily["snapshot_date"].nunique())
    return {
        "hypothesis": "Recent star growth is associated with subsequent fork growth.",
        "status": "READY" if snapshot_count >= minimum_snapshots else "INSUFFICIENT_HISTORY",
        "available_snapshots": snapshot_count,
        "required_snapshots": minimum_snapshots,
        "reason": "Non-overlapping growth windows require longitudinal observations; no synthetic history is used.",
    }


def _extract_number(html: str, key: str) -> int:
    match = re.search(rf'"{re.escape(key)}":(\d+)', html)
    return int(match.group(1)) if match else 0


def _extract_string(html: str, key: str) -> str | None:
    match = re.search(rf'"{re.escape(key)}":"([^"\\]*(?:\\.[^"\\]*)*)"', html)
    return json.loads(f'"{match.group(1)}"') if match else None


def _latest_commit_at(session: requests.Session, full_name: str, default_branch: str) -> str | None:
    response = session.get(f"https://github.com/{full_name}/commits/{default_branch}.atom", timeout=30)
    if response.status_code != 200:
        return None
    root = ET.fromstring(response.text)
    entry = root.find("{http://www.w3.org/2005/Atom}entry")
    updated = entry.find("{http://www.w3.org/2005/Atom}updated") if entry is not None else None
    return updated.text if updated is not None else None


def _open_issue_count(session: requests.Session, full_name: str) -> int:
    response = session.get(f"https://github.com/{full_name}/issues?q=is%3Aissue+is%3Aopen", timeout=30)
    if response.status_code != 200:
        return 0
    match = re.search(r'data-content="Issues".{0,300}CounterLabel[^>]*>([\d,]+)</span>', response.text, re.DOTALL)
    return int(match.group(1).replace(",", "")) if match else 0


def collect_public_github_snapshot(*, pages: int = 5, snapshot_date: str | None = None) -> list[dict[str, Any]]:
    """Collect public evidence without a token when GitHub's API quota is exhausted.

    Production ingestion remains API-based. This bounded HTML collector exists so a
    reviewer can reproduce the portfolio analysis without cloud credentials.
    """
    snapshot_date = snapshot_date or date.today().isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    names: list[str] = []
    for page in range(1, pages + 1):
        response = session.get(
            "https://github.com/search",
            params={"q": "topic:data-engineering language:Python", "type": "repositories", "s": "stars", "o": "desc", "p": page},
            timeout=30,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        names.extend(a.get("href", "").strip("/") for a in soup.select('[data-testid="results-list"] h3 a'))

    records: list[dict[str, Any]] = []
    for full_name in dict.fromkeys(name for name in names if name.count("/") == 1):
        response = session.get(f"https://github.com/{full_name}", timeout=30)
        response.raise_for_status()
        html = response.text
        repo_id_match = re.search(r'octolytics-dimension-repository_id" content="(\d+)"', html)
        default_branch = _extract_string(html, "defaultBranch") or "main"
        owner, name = full_name.split("/", 1)
        description_tag = BeautifulSoup(html, "html.parser").find("meta", {"name": "description"})
        records.append(
            {
                "id": int(repo_id_match.group(1)) if repo_id_match else int(hashlib.sha256(full_name.encode()).hexdigest()[:12], 16),
                "full_name": full_name,
                "name": name,
                "owner": {"login": owner},
                "html_url": f"https://github.com/{full_name}",
                "description": description_tag.get("content") if description_tag else None,
                "stargazers_count": _extract_number(html, "stargazerCount"),
                "forks_count": _extract_number(html, "forksCount"),
                "open_issues_count": _open_issue_count(session, full_name),
                "created_at": _extract_string(html, "createdAt"),
                "pushed_at": _latest_commit_at(session, full_name, default_branch),
                "archived": '"isArchived":true' in html,
                "snapshot_date": snapshot_date,
            }
        )
        time.sleep(0.08)
    return records


def new_run_id(snapshot_date: str) -> str:
    return f"github-{snapshot_date}-{uuid4().hex[:12]}"


def write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
