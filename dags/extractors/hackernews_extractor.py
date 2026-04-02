import logging
from typing import Any, Dict, List, Optional

import requests
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from extractors.s3_utils import upload_json_to_s3


class _RetryableHTTPError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type(_RetryableHTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(6),
)
def _get_json(url: str) -> Any:
    try:
        response = requests.get(
            url,
            headers={"Accept": "application/json", "User-Agent": "dev-ecosystem-pipeline/1.0"},
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        # Treat transient TLS / connection issues as retryable.
        raise _RetryableHTTPError(f"Hacker News request error: {exc.__class__.__name__}") from exc

    if response.status_code in (429, 500, 502, 503, 504):
        raise _RetryableHTTPError(f"Hacker News temporary failure: status={response.status_code}")
    if response.status_code != 200:
        raise RuntimeError(f"Hacker News API error: status={response.status_code} body={response.text[:200]}")
    return response.json()


def _hn_item_to_post(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # We only keep "story" items; HN includes comments/jobs/polls/etc.
    if item.get("type") != "story":
        return None

    item_id = item.get("id")
    if not item_id:
        return None

    # Map Hacker News fields into our "community posts" schema (previously Reddit-shaped)
    # so we don't need to touch dbt models.
    return {
        "id": str(item_id),
        "subreddit": "hackernews",
        "title": item.get("title"),
        "score": item.get("score", 0),
        "num_comments": item.get("descendants", 0),
        "author": item.get("by"),
        "created_utc": int(item.get("time", 0)),
        "url": item.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
        "is_self": item.get("url") is None,
        "permalink": f"https://news.ycombinator.com/item?id={item_id}",
    }


def extract_hackernews_posts(*, run_date: str, limit: int = 100) -> str:
    """
    Extract Hacker News posts (no auth) and upload raw JSON to S3.

    S3 key: raw/hackernews/{YYYY-MM-DD}/posts.json
    """
    # Firebase-backed endpoints (official HN API).
    top_ids: List[int] = _get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
    top_ids = top_ids[:limit]

    posts: List[Dict[str, Any]] = []
    for item_id in top_ids:
        try:
            item = _get_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
        except RetryError as exc:
            logging.warning("Skipping HN item_id=%s after retries (%s)", item_id, exc)
            continue

        mapped = _hn_item_to_post(item)
        if mapped:
            posts.append(mapped)

    logging.info("Extracted %d Hacker News story posts (limit=%d)", len(posts), limit)

    key = f"raw/hackernews/{run_date}/posts.json"
    upload_json_to_s3(data=posts, key=key)
    return key
