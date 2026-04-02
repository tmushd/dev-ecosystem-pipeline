import logging
import time
from typing import Any, Dict, List

import requests
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from extractors.s3_utils import upload_json_to_s3


class _RetryableHTTPError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type(_RetryableHTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(6),
)
def _get_json(url: str, params: Dict[str, Any]) -> Any:
    response = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json", "User-Agent": "dev-ecosystem-pipeline/1.0"},
        timeout=30,
    )
    if response.status_code in (429, 500, 502, 503, 504):
        raise _RetryableHTTPError(
            f"CoinGecko temporary failure: status={response.status_code} url={url}"
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"CoinGecko API error: status={response.status_code} body={response.text[:500]}"
        )
    return response.json()


def extract_coingecko(*, run_date: str) -> List[str]:
    """
    Extract CoinGecko markets + price history and upload raw JSON to S3.

    S3 keys:
    - raw/coingecko/{YYYY-MM-DD}/markets.json
    - raw/coingecko/{YYYY-MM-DD}/price_history.json
    """
    markets = _get_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
        },
    )

    markets_key = f"raw/coingecko/{run_date}/markets.json"
    upload_json_to_s3(data=markets, key=markets_key)

    # Price history is a separate endpoint; keep the request volume reasonable
    # while still demonstrating multi-endpoint extraction.
    top_coin_ids = [c.get("id") for c in markets[:3] if c.get("id")]
    logging.info("Fetching CoinGecko price history for %d coins", len(top_coin_ids))

    history_payload: List[Dict[str, Any]] = []
    for coin_id in top_coin_ids:
        # CoinGecko free tier is rate-limited; space out calls proactively to avoid 429s.
        time.sleep(4.0)
        try:
            history = _get_json(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": 365},
            )
            history_payload.append({"coin_id": coin_id, "market_chart": history})
        except RetryError as exc:
            logging.warning(
                "CoinGecko price history failed for coin_id=%s after retries; skipping. (%s)",
                coin_id,
                exc,
            )

    history_key = f"raw/coingecko/{run_date}/price_history.json"
    upload_json_to_s3(data=history_payload, key=history_key)

    return [markets_key, history_key]
