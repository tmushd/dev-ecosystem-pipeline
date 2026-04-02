import logging
import os

from dotenv import load_dotenv
import snowflake.connector


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv()

    conn = snowflake.connector.connect(
        account=_required_env("SNOWFLAKE_ACCOUNT"),
        user=_required_env("SNOWFLAKE_USER"),
        password=_required_env("SNOWFLAKE_PASSWORD"),
        warehouse=_required_env("SNOWFLAKE_WAREHOUSE"),
        database=_required_env("SNOWFLAKE_DATABASE"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    )

    tables = [
        "RAW.RAW_GITHUB_REPOS",
        "RAW.RAW_COINGECKO_MARKETS",
        "RAW.RAW_COINGECKO_PRICE_HISTORY",
        "RAW.RAW_REDDIT_POSTS",
    ]

    with conn:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"{table}: {count}")


if __name__ == "__main__":
    main()

