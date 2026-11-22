with source_counts as (
    select snapshot_date, count(*) as source_rows
    from {{ ref('stg_github_repos') }}
    group by snapshot_date
), target_counts as (
    select snapshot_date, count(*) as target_rows
    from {{ ref('fct_repo_daily') }}
    group by snapshot_date
)
select coalesce(s.snapshot_date, t.snapshot_date) as snapshot_date, s.source_rows, t.target_rows
from source_counts s
full outer join target_counts t using (snapshot_date)
where coalesce(s.source_rows, -1) <> coalesce(t.target_rows, -1)
