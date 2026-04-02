#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${repo_root}/.env" ]]; then
  # Export variables from .env into the current shell so dbt can read env_var(...)
  set -a
  # shellcheck disable=SC1091
  source "${repo_root}/.env"
  set +a
fi

# Activate the local virtualenv so `dbt` points to the right install.
# shellcheck disable=SC1091
source "${repo_root}/.venv/bin/activate"

export DBT_PROFILES_DIR="${repo_root}/dbt_project"

cd "${repo_root}/dbt_project"
exec dbt "$@"

