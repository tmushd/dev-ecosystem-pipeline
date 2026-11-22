with source as (
    select * from {{ source('raw', 'raw_github_repos') }}
),
typed as (
    select
        snapshot_key,
        try_to_number(raw_data:id) as repo_id,
        raw_data:full_name::string as repo_full_name,
        raw_data:owner:login::string as owner_login,
        raw_data:name::string as repo_name,
        raw_data:html_url::string as html_url,
        raw_data:description::string as description,
        greatest(try_to_number(raw_data:stargazers_count), 0) as stars,
        greatest(try_to_number(raw_data:forks_count), 0) as forks,
        greatest(try_to_number(raw_data:open_issues_count), 0) as open_issues,
        try_to_timestamp_tz(raw_data:created_at::string) as created_at,
        try_to_timestamp_tz(raw_data:pushed_at::string) as last_push_at,
        coalesce(try_to_boolean(raw_data:archived), false) as is_archived,
        snapshot_date,
        source_file,
        run_id,
        ingested_at
    from source
)
select * from typed
where repo_id is not null and snapshot_date is not null
