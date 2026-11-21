select *
from {{ ref('fct_repo_daily') }}
where stars < 0 or forks < 0 or open_issues < 0
