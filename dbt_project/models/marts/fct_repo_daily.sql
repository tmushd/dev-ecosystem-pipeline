{{ config(materialized='incremental', unique_key='snapshot_key', incremental_strategy='merge') }}

select
    snapshot_key,
    repo_id,
    repo_full_name,
    owner_login,
    repo_name,
    html_url,
    description,
    stars,
    forks,
    open_issues,
    created_at,
    last_push_at,
    is_archived,
    snapshot_date,
    greatest(datediff('day', to_date(last_push_at), snapshot_date), 0) as days_since_last_push,
    greatest(datediff('day', to_date(created_at), snapshot_date), 1) as repo_age_days,
    days_since_last_push <= 30 as is_recently_maintained_30d,
    forks / nullif(stars, 0) as fork_to_star_ratio,
    open_issues / nullif(stars, 0) as issue_to_star_ratio,
    source_file,
    run_id,
    ingested_at
from {{ ref('stg_github_repos') }}
{% if is_incremental() %}
where ingested_at >= (select coalesce(max(ingested_at), '1900-01-01') from {{ this }})
{% endif %}
