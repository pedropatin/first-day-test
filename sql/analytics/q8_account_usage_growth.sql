-- Q8. Accounts with usage growth over the three-day sample.
-- Definition: usage = total valid events per day. Growth = last-day usage
-- vs first-day usage for accounts active on both boundary days of the
-- sample. Three days is far too short to call a trend; this surfaces
-- direction, not a verdict (also flagged in the README).

with bounds as (
    select min(event_date) as first_day, max(event_date) as last_day
    from daily_account_metrics
),

pivoted as (
    select
        metrics.account_id,
        metrics.account_name,
        sum(events) filter (event_date = bounds.first_day) as first_day_events,
        sum(events) filter (event_date = bounds.last_day)  as last_day_events,
        sum(events)                                        as total_events
    from daily_account_metrics as metrics, bounds
    group by metrics.account_id, metrics.account_name
)

select
    account_id,
    account_name,
    first_day_events,
    last_day_events,
    total_events,
    last_day_events - first_day_events as absolute_growth,
    round(
        100.0 * (last_day_events - first_day_events)
        / nullif(first_day_events, 0), 1
    ) as growth_pct
from pivoted
where first_day_events is not null and last_day_events is not null
order by growth_pct desc;
