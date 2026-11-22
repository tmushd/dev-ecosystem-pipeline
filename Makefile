.PHONY: install test lint dbt-parse evidence verify

install:
	python3 -m pip install -r requirements.txt

test:
	python3 -m pytest

lint:
	python3 -m ruff check analytics dags/extractors scripts tests

dbt-parse:
	dbt parse --project-dir dbt_project --profiles-dir ci/dbt --no-partial-parse

evidence:
	python3 scripts/build_portfolio_evidence.py --pages 5

verify: test lint dbt-parse evidence
	python3 scripts/verify_release.py
