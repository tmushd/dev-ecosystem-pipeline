import argparse
import os

from dotenv import load_dotenv


def _missing(names):
    return [name for name in names if not os.getenv(name)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate required environment variables without printing secrets."
    )
    parser.add_argument(
        "--scope",
        default="all",
        choices=["github", "coingecko", "hackernews", "snowflake", "all"],
        help="Check only the variables needed for a specific step.",
    )
    args = parser.parse_args()

    load_dotenv()

    common = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME"]
    scope_map = {
        "github": common + ["GITHUB_TOKEN"],
        "coingecko": common,
        "hackernews": common,
        "snowflake": common
        + [
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_WAREHOUSE",
        ],
        "all": common
        + [
            "GITHUB_TOKEN",
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_WAREHOUSE",
        ],
    }

    required = scope_map[args.scope]
    missing = _missing(required)
    if missing:
        print(f"Missing env vars for scope={args.scope}:")
        for name in missing:
            print(f"- {name}")
        raise SystemExit(1)

    print(f"All required env vars are present for scope={args.scope}.")


if __name__ == "__main__":
    main()
