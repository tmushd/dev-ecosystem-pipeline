import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from extractors.s3_utils import upload_json_to_s3


class _RetryableGitHubError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type(_RetryableGitHubError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(6),
)
def _search_page(*, page: int, headers: dict[str, str]) -> requests.Response:
    response = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": "topic:data-engineering language:python", "sort": "stars", "per_page": 100, "page": page},
        headers=headers,
        timeout=30,
    )
    if response.status_code in (429, 500, 502, 503, 504):
        raise _RetryableGitHubError(f"temporary GitHub failure: status={response.status_code}")
    return response


def extract_github_repos(*, run_date: str, run_id: str | None = None) -> str:
    """
    Extract GitHub repos via the REST API and upload raw JSON to S3.

    S3 key: raw/github/{YYYY-MM-DD}/repos.json
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("Missing required env var: GITHUB_TOKEN")

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "open-source-ecosystem-intelligence/2.0"}
    run_id = run_id or f"github-{run_date}-{uuid4().hex[:12]}"
    extracted_at = datetime.now(timezone.utc).isoformat()

    all_repos: list[dict[str, Any]] = []
    page = 1

    # Keep the same pagination + rate limit behavior as the original design:
    # loop pages until the API returns no more items.
    while True:
        logging.info("GitHub search: fetching page=%d", page)
        response = _search_page(page=page, headers=headers)

        # Handle rate limiting (Search API often returns 403 when exhausted).
        if response.status_code == 403:
            reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
            wait_seconds = max(reset_time - time.time(), 0) + 5
            logging.warning("GitHub rate limited. Waiting %.0fs...", wait_seconds)
            time.sleep(wait_seconds)
            continue

        # Search API only returns the first 1000 results (10 pages at 100/page).
        # Past that, GitHub responds with HTTP 422.
        if response.status_code == 422 and "Only the first 1000 search results" in response.text:
            logging.info("GitHub search reached 1000-result cap; stopping pagination.")
            break

        if response.status_code != 200:
            raise RuntimeError(
                f"GitHub API error: status={response.status_code} body={response.text[:500]}"
            )

        data = response.json()
        repos = data.get("items", [])
        if not repos:
            break

        for repo in repos:
            repo["_ingestion_metadata"] = {
                "run_id": run_id,
                "snapshot_date": run_date,
                "extracted_at": extracted_at,
                "source": "github_search_api",
                "schema_version": 2,
            }
        all_repos.extend(repos)
        page += 1

        # Respect rate limits proactively.
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining < 5:
            logging.info("GitHub rate limit low (%d remaining). Sleeping 10s...", remaining)
            time.sleep(10)

    logging.info("Extracted %d GitHub repos across %d pages", len(all_repos), page - 1)

    key = f"raw/github/{run_date}/repos.json"
    upload_json_to_s3(data=all_repos, key=key)

    return key
