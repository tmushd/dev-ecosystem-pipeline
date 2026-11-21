select *
from {{ ref('fct_repo_daily') }}
where created_at is null
   or last_push_at is null
   or last_push_at < created_at
   or snapshot_date < to_date(created_at)
