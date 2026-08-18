# Production design note

How this pipeline would evolve from a 3-file local exercise into production.
The local layering (immutable raw → explainable rejects → tested marts) is
the part that survives unchanged; everything below is about scale and
operations around it.

## Batch vs streaming

Start batch. Events land in object storage (S3) as hourly/daily files,
partitioned by received date; a scheduled job (Airflow/Dagster, or even cron)
ingests new files and runs `dbt build`. Batch is right as long as the
freshest consumer is a daily metrics dashboard.

Move to streaming only when a consumer needs sub-hour data (e.g. live cost
guardrails). Then: events → Kinesis/Kafka → micro-batch append into the raw
layer — the dbt layer doesn't change, only ingestion cadence does. Late
events are already handled by design (dated by `event_ts`, flagged), so
lateness doesn't force streaming.

## Schema evolution

The raw layer stores the full original payload (`raw_payload`), so new
properties arrive without breaking anything — they're just not extracted yet.
Promoting a new field is a staging-model change plus a dbt test, reviewed
like any code change. Unknown `event_name` values are quarantined in
`rejected_events`, which doubles as a discovery queue: a recurring unknown
name (like `assistant_hovered` in this sample) is a signal to either add it
to the contract or fix the emitter. For stronger guarantees, add a schema
registry / event contract validated at the producer side.

## Data quality and alerting

Same checks, promoted to gates:

- dbt tests run in CI on every PR against a sample, and after every
  production build; failures block downstream models.
- The validation report becomes metrics (reject rate by reason, volume by
  event_name) emitted to monitoring. Alert on reject-rate spikes and volume
  anomalies rather than absolute numbers.
- `rejected_events` retains file + line + reason, so every alert is
  debuggable down to the exact input line.

## Backfills and idempotency

Ingestion is already idempotent per source file (delete-by-file + insert),
and the dbt layer is a pure function of the raw layer. A backfill is:
re-drop the affected files, re-ingest, `dbt build`. At scale, partition raw
tables by date and make marts incremental with late-arrival lookback windows
(e.g. reprocess the trailing 3 days), keeping full-refresh as the recovery
path.

## PII

Emails are the only PII in this dataset; marts expose only the masked domain
(`dim_users.email_masked`). In production:

- classify columns at the source; PII never leaves the raw layer, which
  lives in a restricted schema;
- analyst-facing layers get masked or tokenized values by default, with
  audited access to raw for the few who need it;
- deletion requests (GDPR/CCPA) are handled by user_id: delete from raw,
  rebuild downstream — possible only because everything derives from raw.

## Cost monitoring

`daily_account_metrics.ai_cost_usd` plus `uncosted_interactions` is the
foundation: never trust a cost total without knowing how much of it is
missing. Add: reconciliation of event-reported cost against provider
invoices (they drift), per-account/model daily anomaly detection (a z-score
over trailing 14 days is enough to start), and margin views (cost vs plan)
for finance.

## Exposing the data

DuckDB/MotherDuck or a warehouse (Snowflake/BigQuery) as the query layer;
marts are the only supported interface — analysts never touch raw. dbt docs
give lineage and column descriptions; BI (Metabase/Looker) points at marts;
internal tools read the same tables via a thin API. Metric definitions live
in the dbt layer once, not re-derived per dashboard.

## Intentionally skipped (time budget)

- Orchestrator (Makefile is the DAG at this size).
- Incremental models — full rebuild takes under a second here.
- CI pipeline, containerization.
- Strict funnel stage ordering by timestamp (flags are "ever happened").
- Cost anomaly detection and seat-utilization metrics.
