with history as (
    select
        *,
        stars - lag(stars) over (partition by repo_id order by snapshot_date) as star_growth,
        forks - lag(forks) over (partition by repo_id order by snapshot_date) as fork_growth,
        count(*) over (partition by repo_id) as snapshot_count,
        percent_rank() over (partition by snapshot_date order by stars) as star_percentile,
        percent_rank() over (partition by snapshot_date order by forks) as fork_percentile
    from {{ ref('fct_repo_daily') }}
), scored as (
    select
        *,
        round(100 * (
            0.40 * exp(-days_since_last_push / 45.0)
            + 0.35 * star_percentile
            + 0.25 * fork_percentile
        ), 2) as evaluation_score,
        case
            when days_since_last_push > 180 then 'HIGH'
            when days_since_last_push > 90 then 'WATCH'
            else 'ACTIVE'
        end as maintenance_risk,
        case when snapshot_count >= 14 then 'READY_FOR_LONGITUDINAL_ANALYSIS' else 'COLLECTING_HISTORY' end as growth_evidence_status
    from history
)
select * from scored
qualify snapshot_date = max(snapshot_date) over ()
