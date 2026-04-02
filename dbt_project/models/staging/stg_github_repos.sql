select
  raw_data
from {{ source('raw', 'raw_github_repos') }}

