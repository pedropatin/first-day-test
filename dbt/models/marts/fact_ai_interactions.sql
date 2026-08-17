-- Grain: one row per AI model call — i.e. one `ai_response_generated` event.
-- Cost columns:
--   * cost_usd            — as reported by the event; NULL when missing.
--   * cost_usd_estimated  — cost_usd when known, otherwise imputed as
--     total_tokens x the model's observed cost-per-token (derived from this
--     sample's costed calls). is_cost_estimated marks imputed rows, so both
--     "known cost" and "estimated cost" totals stay computable.
-- `accepted` is the flag emitted on the generation event itself; explicit
-- response_accepted / response_rejected events are aggregated in fact_sessions.

with interactions as (

    select * from {{ ref('stg_events') }}
    where event_name = 'ai_response_generated'

),

model_rates as (

    select
        model,
        sum(cost_usd) / sum(total_tokens) as usd_per_token
    from interactions
    where cost_usd is not null and total_tokens > 0
    group by model

)

select
    interactions.event_id   as interaction_id,
    interactions.event_ts,
    interactions.event_date,
    interactions.account_id,
    interactions.user_id,
    interactions.session_id,
    interactions.workflow,
    interactions.model,
    interactions.prompt_tokens,
    interactions.completion_tokens,
    interactions.total_tokens,
    interactions.latency_ms,
    interactions.cost_usd,
    coalesce(
        interactions.cost_usd,
        round(model_rates.usd_per_token * interactions.total_tokens, 6)
    ) as cost_usd_estimated,
    interactions.cost_usd is null as is_cost_estimated,
    interactions.accepted,
    interactions.is_late
from interactions
left join model_rates using (model)
