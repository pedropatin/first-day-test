-- Grain: one row per account (account_id is the natural key).

select
    account_id,
    account_name,
    plan,
    industry,
    seat_limit,
    created_at as account_created_at
from {{ source('raw', 'raw_accounts') }}
