-- Q5. Session conversion funnel.
-- Share of started sessions where each stage EVER happened, cumulatively
-- (a stage only counts if all previous stages happened too); no strict
-- intra-session timestamp ordering required. Base = sessions with a
-- session_started event.

with base as (

    select * from {{ ref('fact_sessions') }}
    where has_session_started

),

funnel as (
    select 1 as stage_order, 'session_started' as stage, count(*) as sessions
    from base
    union all
    select 2, 'prompt_submitted', count(*) from base
    where has_prompt_submitted
    union all
    select 3, 'ai_response_generated', count(*) from base
    where has_prompt_submitted and has_ai_response
    union all
    select 4, 'response_accepted', count(*) from base
    where has_prompt_submitted and has_ai_response and has_response_accepted
    union all
    select 5, 'workflow_completed', count(*) from base
    where has_prompt_submitted and has_ai_response
      and has_response_accepted and has_workflow_completed
)

select
    stage_order,
    stage,
    sessions,
    round(100.0 * sessions / first_value(sessions) over (order by stage_order), 1)
        as pct_of_started
from funnel
order by stage_order
