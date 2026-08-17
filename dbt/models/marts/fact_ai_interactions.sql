-- Grain: one row per AI model call — i.e. one `ai_response_generated` event.
-- Assumptions:
--   * cost_usd is missing on some calls; it is kept NULL (not imputed) so
--     SUM() gives "known cost" — daily_account_metrics documents the same.
--   * `accepted` here is the flag emitted on the generation event itself;
--     explicit response_accepted / response_rejected events are separate
--     rows in stg_events and are aggregated in fact_sessions.

select
    event_id            as interaction_id,
    event_ts,
    event_date,
    account_id,
    user_id,
    session_id,
    workflow,
    model,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    latency_ms,
    cost_usd,
    accepted,
    is_late
from {{ ref('stg_events') }}
where event_name = 'ai_response_generated'
