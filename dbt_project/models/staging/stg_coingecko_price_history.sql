select
  raw_data
from {{ source('raw', 'raw_coingecko_price_history') }}

