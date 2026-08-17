-- Grain: one row per session (session_id).
-- Assumptions:
--   * A session belongs to the account/user of its earliest event; the data
--     never shows a session spanning users, but the rule is deterministic
--     either way.
--   * session_date is the date of the first event in the session (a session
--     crossing midnight counts once, on its start date).
--   * Funnel flags mark whether each stage EVER happened in the session;
--     they do not require strict timestamp ordering between stages.

with events as (

    select * from {{ ref('stg_events') }}
    where session_id is not null

),

session_owner as (

    select
        session_id,
        account_id,
        user_id
    from events
    qualify row_number() over (
        partition by session_id
        order by event_ts, event_id
    ) = 1

),

aggregated as (

    select
        session_id,
        min(event_ts)                                            as started_at,
        max(event_ts)                                            as ended_at,
        cast(min(event_ts) as date)                              as session_date,
        max(workflow)                                            as workflow,

        count(*)                                                 as event_count,
        count(*) filter (event_name = 'prompt_submitted')        as prompts_submitted,
        count(*) filter (event_name = 'ai_response_generated')   as ai_responses,
        count(*) filter (event_name = 'response_accepted')       as responses_accepted,
        count(*) filter (event_name = 'response_rejected')       as responses_rejected,
        count(*) filter (event_name = 'workflow_completed')      as workflows_completed,
        count(*) filter (event_name = 'error_raised')            as errors_raised,

        sum(total_tokens)                                        as total_tokens,
        sum(cost_usd)                                            as cost_usd,

        bool_or(event_name = 'session_started')                  as has_session_started,
        bool_or(event_name = 'prompt_submitted')                 as has_prompt_submitted,
        bool_or(event_name = 'ai_response_generated')            as has_ai_response,
        bool_or(event_name = 'response_accepted')                as has_response_accepted,
        bool_or(event_name = 'workflow_completed')                as has_workflow_completed

    from events
    group by session_id

)

select
    aggregated.session_id,
    session_owner.account_id,
    session_owner.user_id,
    aggregated.* exclude (session_id),
    date_diff('second', aggregated.started_at, aggregated.ended_at)
        as duration_seconds
from aggregated
join session_owner using (session_id)
