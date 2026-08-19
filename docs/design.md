# Production design note

This note describes how I would extend the local pipeline if it had to support
production data and users. I would keep the separation between raw data,
explainable rejections, and tested marts, while changing the storage and
orchestration around those layers.

## Batch vs streaming

I would start with batch ingestion. Events would land in object storage as
hourly or daily files partitioned by received date. A scheduled job would load
new files and run `dbt build`. This is sufficient while the main consumer is a
daily metrics dashboard.

Streaming would only be justified by a concrete low-latency requirement, such
as live cost guardrails. In that case, Kafka or Kinesis could write
micro-batches into the same raw layer. Late events would still be grouped by
`event_ts` and monitored through the existing late-arrival flag.

## Schema evolution

The raw layer stores the full parsed payload (`raw_payload`), so new properties
can arrive without immediately breaking downstream models; they remain
available even before they are promoted to typed columns.
Promoting a new field is a staging-model change plus a dbt test, reviewed
like any code change. Unknown `event_name` values are quarantined in
`rejected_events`, which doubles as a discovery queue: a recurring unknown
name (like `assistant_hovered` in this sample) is a signal to either add it
to the contract or fix the emitter. For stronger guarantees, add a schema
registry / event contract validated at the producer side.

## Data quality and alerting

The repository already runs the fixture tests and full local pipeline in
GitHub Actions for pull requests and pushes to `main`. In production I would
extend the same checks into operational gates:

- dbt tests run after every production build, with failures blocking
  downstream models.
- The validation report becomes metrics (reject rate by reason, volume by
  event_name) emitted to monitoring. Alert on reject-rate spikes and volume
  anomalies rather than absolute numbers.
- `rejected_events` retains file + line + reason, so every alert is
  debuggable down to the exact input line.

## Backfills and idempotency

The local ingestion is idempotent for each source file: it deletes that file's
current rows before inserting the replacement. A local backfill is therefore a
re-ingestion of the affected files followed by `dbt build`. In production I
would wrap file replacement in a transaction, record a file checksum and load
status, partition raw tables by date, and make large marts incremental. A
lookback window would reprocess recent partitions for late arrivals, while a
full refresh would remain available as a recovery path.

## PII

Emails are the only obvious PII in this dataset. The mart exposes only the
masked domain (`dim_users.email_masked`). In production I would also:

- classify columns at the source; PII never leaves the raw layer, which
  lives in a restricted schema;
- analyst-facing layers get masked or tokenized values by default, with
  audited access to raw for the few who need it;
- deletion requests (GDPR/CCPA) are handled by user_id: delete from raw,
  rebuild downstream — possible only because everything derives from raw.

## Cost monitoring

`daily_account_metrics.ai_cost_usd` and `uncosted_interactions` provide the
starting point. I would reconcile event-reported cost against provider
invoices, alert on unusual daily cost by account and model, and add finance
views that compare model cost with account revenue. Estimated and reported
costs should remain separate in those views.

## Exposing the data

DuckDB/MotherDuck or a warehouse (Snowflake/BigQuery) as the query layer;
marts are the only supported interface — analysts never touch raw. dbt docs
give lineage and column descriptions; BI (Metabase/Looker) points at marts;
internal tools read the same tables via a thin API. Metric definitions live
in the dbt layer once, not re-derived per dashboard.

## Intentionally skipped (time budget)

- Orchestrator (Makefile is the DAG at this size).
- Incremental models — full rebuild takes under a second here.
- Containerization.
- Strict funnel stage ordering by timestamp (flags are "ever happened").
- Cost anomaly detection and seat-utilization metrics.
