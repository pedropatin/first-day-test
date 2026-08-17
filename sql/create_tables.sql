-- Raw layer DDL. Executed by src/ingest.py on every run (idempotent).
-- Raw tables preserve source values as-is (timestamps kept as VARCHAR);
-- typing/casting happens in the dbt staging layer so that bad values can be
-- rejected with a reason instead of failing the load.

CREATE TABLE IF NOT EXISTS raw_events (
    event_id      VARCHAR,          -- may be NULL/duplicated in raw; cleaned in staging
    event_ts      VARCHAR,          -- raw string, cast + validated in staging
    received_ts   VARCHAR,
    account_id    VARCHAR,
    user_id       VARCHAR,
    session_id    VARCHAR,
    event_name    VARCHAR,
    properties    JSON,             -- flattened in staging
    raw_payload   JSON,             -- full original line for lineage/debugging
    source_file   VARCHAR NOT NULL,
    line_number   INTEGER NOT NULL,
    ingested_at   TIMESTAMP NOT NULL
);

-- Lines that could not be parsed as a JSON event object at ingestion time.
-- Staging-level rejections (bad values, unknown refs, duplicates) are unioned
-- with these in the dbt model `rejected_events`.
CREATE TABLE IF NOT EXISTS raw_ingest_rejections (
    source_file      VARCHAR NOT NULL,
    line_number      INTEGER NOT NULL,
    raw_line         VARCHAR,
    rejection_reason VARCHAR NOT NULL,
    ingested_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_accounts (
    account_id   VARCHAR,
    account_name VARCHAR,
    plan         VARCHAR,
    industry     VARCHAR,
    seat_limit   INTEGER,
    created_at   TIMESTAMP,
    source_file  VARCHAR NOT NULL,
    ingested_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_users (
    user_id     VARCHAR,
    account_id  VARCHAR,
    email       VARCHAR,
    role        VARCHAR,
    status      VARCHAR,
    created_at  TIMESTAMP,
    source_file VARCHAR NOT NULL,
    ingested_at TIMESTAMP NOT NULL
);
