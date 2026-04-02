import argparse
import logging
import os
import sys
from datetime import date

import boto3
from dotenv import load_dotenv


def _head_object(bucket: str, key: str) -> None:
    region = os.environ["AWS_REGION"]
    s3 = boto3.client("s3", region_name=region)
    s3.head_object(Bucket=bucket, Key=key)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Run Hacker News extractor locally and verify S3 upload."
    )
    parser.add_argument(
        "--run-date",
        default=date.today().isoformat(),
        help="Run date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument("--limit", type=int, default=100, help="Number of top items to fetch.")
    args = parser.parse_args()

    load_dotenv()

    dags_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "dags"))
    if dags_dir not in sys.path:
        sys.path.insert(0, dags_dir)

    from extractors.hackernews_extractor import extract_hackernews_posts

    key = extract_hackernews_posts(run_date=args.run_date, limit=args.limit)
    bucket = os.environ["S3_BUCKET_NAME"]

    _head_object(bucket, key)
    print(f"OK: uploaded and verified s3://{bucket}/{key}")


if __name__ == "__main__":
    main()

