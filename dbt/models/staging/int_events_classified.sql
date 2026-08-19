-- Grain: one row per raw_events row (duplicates still present).
-- Types every field, flattens `properties`, and assigns at most one
-- `rejection_reason` per row (first failing rule wins, in documented
-- priority order). Rows with rejection_reason IS NULL feed stg_events;
-- the rest feed rejected_events. Deduplication happens here too: among
-- valid rows sharing an event_id, the row with the earliest
-- (received_ts, source_file, line_number) is kept — a deterministic
-- "first received wins" rule — and later copies are marked
-- 'duplicate_event_id'.

with typed as (

    select
        event_id,
        try_cast(event_ts as timestamp)    as event_ts,
        event_ts                           as event_ts_raw,
        try_cast(received_ts as timestamp) as received_ts,
        account_id,
        user_id,
        session_id,
        event_name,

        json_extract_string(properties, '$.workflow')             as workflow,
        json_extract_string(properties, '$.model')                as model,
        try_cast(json_extract(properties, '$.prompt_tokens')      as integer) as prompt_tokens,
        try_cast(json_extract(properties, '$.completion_tokens')  as integer) as completion_tokens,
        try_cast(json_extract(properties, '$.latency_ms')         as integer) as latency_ms,
        try_cast(json_extract(properties, '$.cost_usd')           as double)  as cost_usd,
        try_cast(json_extract(properties, '$.accepted')           as boolean) as accepted,
        try_cast(json_extract(properties, '$.duration_ms')        as integer) as duration_ms,
        try_cast(json_extract(properties, '$.prompt_length_chars') as integer) as prompt_length_chars,
        json_extract_string(properties, '$.device')                as device,
        json_extract_string(properties, '$.error_code')            as error_code,
        json_extract_string(properties, '$.reason')                as rejected_reason_text,
        json_extract_string(properties, '$.invite_channel')        as invite_channel,

        -- Missing optional properties and explicit JSON nulls are allowed.
        -- A present value must still match its contract; otherwise try_cast
        -- would silently turn bad input (for example "fast" latency) into NULL.
        coalesce(json_type(properties, '$.prompt_tokens')
                 not in ('BIGINT', 'UBIGINT', 'NULL'), false)
        or coalesce(json_type(properties, '$.completion_tokens')
                    not in ('BIGINT', 'UBIGINT', 'NULL'), false)
        or coalesce(json_type(properties, '$.latency_ms')
                    not in ('BIGINT', 'UBIGINT', 'NULL'), false)
        or coalesce(json_type(properties, '$.duration_ms')
                    not in ('BIGINT', 'UBIGINT', 'NULL'), false)
        or coalesce(json_type(properties, '$.prompt_length_chars')
                    not in ('BIGINT', 'UBIGINT', 'NULL'), false)
        or coalesce(json_type(properties, '$.cost_usd')
                    not in ('BIGINT', 'UBIGINT', 'DOUBLE', 'NULL'), false)
        or coalesce(json_type(properties, '$.accepted')
                    not in ('BOOLEAN', 'NULL'), false)
            as has_invalid_property_type,

        raw_payload,
        source_file,
        line_number,
        ingested_at

    from {{ source('raw', 'raw_events') }}

),

classified as (

    select
        typed.*,
        users.account_id as user_home_account_id,

        case
            -- 1. identity and parseability
            when typed.event_id is null or typed.event_id = ''
                then 'missing_event_id'
            when typed.event_ts is null
                then 'unparseable_event_ts'
            -- the event-name contract lives in one seed file, shared with
            -- the schema tests and validate.py
            when typed.event_name is null
                 or typed.event_name not in (
                     select event_name from {{ ref('expected_event_names') }}
                 )
                then 'unknown_event_name'

            -- 2. required identifiers (session not required for invite/signup,
            --    which happen outside a product session)
            when typed.account_id is null then 'missing_account_id'
            when typed.user_id is null then 'missing_user_id'
            when typed.session_id is null
                 and typed.event_name not in ('user_invited', 'user_signed_up')
                then 'missing_session_id'

            -- 3. metric sanity
            when typed.has_invalid_property_type
                then 'invalid_property_type'
            when least(
                    coalesce(typed.prompt_tokens, 0),
                    coalesce(typed.completion_tokens, 0),
                    coalesce(typed.latency_ms, 0),
                    coalesce(typed.cost_usd, 0),
                    coalesce(typed.duration_ms, 0),
                    coalesce(typed.prompt_length_chars, 0)
                 ) < 0
                then 'negative_metric_value'

            -- 4. referential integrity against metadata
            when accounts.account_id is null then 'unknown_account'
            when users.user_id is null then 'unknown_user'
            when users.account_id != typed.account_id
                then 'user_account_mismatch'
        end as rejection_reason

    from typed
    left join {{ source('raw', 'raw_accounts') }} as accounts
        on typed.account_id = accounts.account_id
    left join {{ source('raw', 'raw_users') }} as users
        on typed.user_id = users.user_id

),

deduped as (

    select
        *,
        case when rejection_reason is null then
            row_number() over (
                partition by event_id
                order by received_ts nulls last, source_file, line_number
            )
        end as copy_rank

    from classified

)

select
    * exclude (has_invalid_property_type, rejection_reason, copy_rank),
    coalesce(
        rejection_reason,
        case when copy_rank > 1 then 'duplicate_event_id' end
    ) as rejection_reason
from deduped
