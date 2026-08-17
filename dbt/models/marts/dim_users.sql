-- Grain: one row per user (user_id is the natural key).
-- Email is masked to the domain only: marts are the analyst-facing layer and
-- no analytics question here needs the full address (see docs/design.md, PII).

select
    users.user_id,
    users.account_id,
    accounts.account_name,
    '***@' || split_part(users.email, '@', 2) as email_masked,
    users.role,
    users.status,
    users.created_at as user_created_at
from {{ source('raw', 'raw_users') }} as users
left join {{ ref('dim_accounts') }} as accounts using (account_id)
