select
  raw_data
from {{ source('raw', 'raw_reddit_posts') }}

