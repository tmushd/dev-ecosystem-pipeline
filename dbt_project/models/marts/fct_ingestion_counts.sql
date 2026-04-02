select 'github' as source_name, count(*) as row_count from {{ ref('stg_github_repos') }}
union all
select 'coingecko_markets' as source_name, count(*) as row_count from {{ ref('stg_coingecko_markets') }}
union all
select 'coingecko_price_history' as source_name, count(*) as row_count from {{ ref('stg_coingecko_price_history') }}
union all
select 'reddit_posts' as source_name, count(*) as row_count from {{ ref('stg_reddit_posts') }}

