-- Grain: one row per unique, valid event (event_id is unique here).
-- Clean, typed, flattened event stream — the single input for all marts.
-- Late-arriving events are kept and flagged (is_late) rather than dropped;
-- event_date always derives from event_ts (when the user acted), not
-- received_ts (when the pipeline heard about it).

select
    event_id,
    event_ts,
    cast(event_ts as date) as event_date,
    received_ts,
    date_diff('second', event_ts, received_ts) as lateness_seconds,
    date_diff('second', event_ts, received_ts) > 3600 as is_late,

    account_id,
    user_id,
    session_id,
    event_name,

    workflow,
    model,
    prompt_tokens,
    completion_tokens,
    prompt_tokens + completion_tokens as total_tokens,
    latency_ms,
    cost_usd,
    accepted,
    duration_ms,
    prompt_length_chars,
    device,
    error_code,
    rejected_reason_text,
    invite_channel,

    source_file,
    line_number,
    ingested_at

from {{ ref('int_events_classified') }}
where rejection_reason is null
