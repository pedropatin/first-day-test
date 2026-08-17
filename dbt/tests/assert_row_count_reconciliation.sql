-- Every input line must be accounted for exactly once:
--   parsed events + unparseable lines == clean events + rejected rows.
-- Fails (returns a row) if anything was silently dropped or double-counted.

with counts as (
    select
        (select count(*) from {{ source('raw', 'raw_events') }})            as raw_events,
        (select count(*) from {{ source('raw', 'raw_ingest_rejections') }}) as ingest_rejections,
        (select count(*) from {{ ref('stg_events') }})                      as staged,
        (select count(*) from {{ ref('rejected_events') }})                 as rejected
)

select *
from counts
where raw_events + ingest_rejections != staged + rejected
