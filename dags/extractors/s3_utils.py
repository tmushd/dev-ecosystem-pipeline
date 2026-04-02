import json
import logging
import os
from typing import Any

import boto3


def _get_s3_bucket_name() -> str:
    # Prefer the variable name requested in the latest spec, but support
    # BUCKET_NAME for backward compatibility with earlier notes.
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("BUCKET_NAME")
    if not bucket:
        raise ValueError("Missing required env var: S3_BUCKET_NAME")
    return bucket


def _get_aws_region() -> str:
    region = os.getenv("AWS_REGION")
    if not region:
        raise ValueError("Missing required env var: AWS_REGION")
    return region


def upload_json_to_s3(*, data: Any, key: str) -> str:
    """
    Upload JSON-serializable data to S3 as UTF-8 JSON.

    Returns the bucket name used.
    """
    bucket = _get_s3_bucket_name()
    region = _get_aws_region()

    logging.info("Uploading raw JSON to s3://%s/%s", bucket, key)

    s3 = boto3.client("s3", region_name=region)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8",
    )

    logging.info("Upload complete: s3://%s/%s (%d bytes)", bucket, key, len(body))
    return bucket

