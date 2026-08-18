-- Q1. Daily active users by account.
-- Active user = distinct user_id with at least one valid event that day;
-- dates from event_ts, so late-arriving events count on the day they happened.

select
    event_date,
    account_id,
    account_name,
    active_users
from {{ ref('daily_account_metrics') }}
order by event_date, account_id
