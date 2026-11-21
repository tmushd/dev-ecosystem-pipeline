select
    snapshot_key,
    try_to_number(raw_data:id) as story_id,
    raw_data:title::string as title,
    greatest(try_to_number(raw_data:score), 0) as score,
    greatest(try_to_number(raw_data:num_comments), 0) as comment_count,
    raw_data:author::string as author,
    to_timestamp_tz(try_to_number(raw_data:created_utc)) as created_at,
    raw_data:url::string as url,
    snapshot_date,
    source_file,
    run_id,
    ingested_at
from {{ source('raw', 'raw_hackernews_posts') }}
where try_to_number(raw_data:id) is not null
