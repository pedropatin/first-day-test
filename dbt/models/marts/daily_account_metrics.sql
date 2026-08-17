-- Grain: one row per (event_date, account_id) with at least one valid event.
-- Assumptions:
--   * "Active user" = distinct user_id with any valid event that day
--     (invites/signups included — they are real product activity).
--   * Dates come from event_ts (user time), so a late-arriving event lands
--     on the day it happened, not the day it was received.
--   * ai_cost_usd sums only known costs; interactions with missing cost_usd
--     contribute 0 (uncosted_interactions counts them for transparency).
--     ai_cost_usd_estimated fills those gaps with the per-model imputation
--     from fact_ai_interactions.

with events as (

    select * from {{ ref('stg_events') }}

),

estimated_cost as (

    select
        event_date,
        account_id,
        sum(cost_usd_estimated) as ai_cost_usd_estimated
    from {{ ref('fact_ai_interactions') }}
    group by event_date, account_id

),

daily as (

    select
        event_date,
        account_id,

        count(distinct user_id)                                  as active_users,
        count(distinct session_id)                               as sessions,
        count(*)                                                 as events,

        count(*) filter (event_name = 'prompt_submitted')        as prompts_submitted,
        count(*) filter (event_name = 'ai_response_generated')   as ai_interactions,
        count(*) filter (event_name = 'response_accepted')       as responses_accepted,
        count(*) filter (event_name = 'response_rejected')       as responses_rejected,
        count(*) filter (event_name = 'workflow_completed')      as workflows_completed,
        count(*) filter (event_name = 'error_raised')            as errors_raised,

        sum(total_tokens) filter (event_name = 'ai_response_generated')
            as ai_total_tokens,
        coalesce(
            sum(cost_usd) filter (event_name = 'ai_response_generated'), 0
        ) as ai_cost_usd,
        count(*) filter (
            event_name = 'ai_response_generated' and cost_usd is null
        ) as uncosted_interactions

    from events
    group by event_date, account_id

)

select
    daily.event_date,
    daily.account_id,
    accounts.account_name,
    accounts.plan,
    daily.* exclude (event_date, account_id),
    round(coalesce(estimated_cost.ai_cost_usd_estimated, 0), 6)
        as ai_cost_usd_estimated
from daily
left join estimated_cost using (event_date, account_id)
left join {{ ref('dim_accounts') }} as accounts using (account_id)
