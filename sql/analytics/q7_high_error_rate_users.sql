-- Q7. Users with unusually high error rates.
-- Definition: error rate = error_raised events / total events per user.
-- "Unusually high" = above (overall mean rate + 2 standard deviations of
-- per-user rates), with a minimum of 10 events so tiny denominators don't
-- dominate. Both the threshold and every user's rate are shown, so the
-- cutoff is auditable.

with per_user as (
    select
        user_id,
        account_id,
        count(*) as events,
        count(*) filter (event_name = 'error_raised') as errors,
        count(*) filter (event_name = 'error_raised') * 1.0 / count(*)
            as error_rate
    from stg_events
    group by user_id, account_id
),

threshold as (
    select avg(error_rate) + 2 * stddev_pop(error_rate) as cutoff
    from per_user
    where events >= 10
)

select
    per_user.user_id,
    per_user.account_id,
    per_user.events,
    per_user.errors,
    round(100.0 * per_user.error_rate, 2) as error_rate_pct,
    round(100.0 * threshold.cutoff, 2)    as threshold_pct
from per_user, threshold
where per_user.events >= 10
  and per_user.error_rate > threshold.cutoff
order by per_user.error_rate desc;
