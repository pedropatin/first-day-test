-- Grain: one row per rejected input line/event.
-- Single explainable audit trail across both rejection stages:
--   * stage = 'ingest'  — the line never parsed as a JSON event object
--     (captured by src/ingest.py in raw_ingest_rejections);
--   * stage = 'staging' — the event parsed but failed a validation rule or
--     was a duplicate copy (classified in int_events_classified).
-- Every row keeps source_file + line_number so any rejection can be traced
-- back to the exact raw input line.

select
    'ingest'          as rejection_stage,
    rejection_reason,
    cast(null as varchar) as event_id,
    cast(null as varchar) as event_name,
    raw_line          as raw_data,
    source_file,
    line_number,
    ingested_at
from {{ source('raw', 'raw_ingest_rejections') }}

union all

select
    'staging'         as rejection_stage,
    rejection_reason,
    event_id,
    event_name,
    cast(raw_payload as varchar) as raw_data,
    source_file,
    line_number,
    ingested_at
from {{ ref('int_events_classified') }}
where rejection_reason is not null
