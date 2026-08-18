-- Q5. Session conversion funnel.
-- Definition: share of sessions in which each stage EVER happened (stage
-- flags from marts.fact_sessions; no strict intra-session ordering required).
-- Sessions are counted once regardless of how many prompts/responses they
-- contain. The base is all sessions with a session_started event.

with base as (
    select * from marts.fact_sessions
    where has_session_started
),

funnel as (
    select '1_session_started'      as stage, count(*) as sessions from base
    union all
    select '2_prompt_submitted', count(*) from base where has_prompt_submitted
    union all
    select '3_ai_response_generated', count(*) from base
    where has_prompt_submitted and has_ai_response
    union all
    select '4_response_accepted', count(*) from base
    where has_prompt_submitted and has_ai_response and has_response_accepted
    union all
    select '5_workflow_completed', count(*) from base
    where has_prompt_submitted and has_ai_response
      and has_response_accepted and has_workflow_completed
)

select
    stage,
    sessions,
    round(100.0 * sessions / first_value(sessions) over (order by stage), 1)
        as pct_of_started
from funnel
order by stage;
