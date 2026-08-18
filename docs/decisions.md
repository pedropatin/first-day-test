# Technical decisions

Short records of the choices a reviewer might question, with the tradeoff
each one accepts. Newest last.

## 1. dbt instead of transform.py (assignment Option B)

Transformations are versioned, tested SQL models rather than a Python
script. Gains: declarative lineage, 47 schema/data tests running inside the
build, one file per model with its grain documented. Cost: two expected
deliverables exist in dbt form (`src/transform.py` → `dbt/models/`,
`sql/marts.sql` → `dbt/models/marts/`); the README maps them explicitly.

## 2. Parse-only ingestion — all judgment lives in dbt

`src/ingest.py` never drops, casts, or dedups; it preserves every parseable
line verbatim (timestamps as strings, full payload kept). Every rule that
can reject an event is SQL in one model (`int_events_classified`), so
changing a rule never touches the loader, and each rejected row carries an
explicit reason. Cost: bronze stores some garbage by design — that is what
bronze is for.

## 3. Medallion schemas, assignment table names

Physical DuckDB schemas `bronze` / `silver` / `gold` make the layer contract
visible to anyone opening the database, while table names stay exactly what
the assignment expects (`raw_events`, `stg_events`, `dim_accounts`, ...).
Renaming tables to `bronze_events` etc. would force the reviewer to
translate — organization gained nothing from breaking the vocabulary.

## 4. Deduplication in staging, not ingestion; first-received wins

The assignment places dedup under ingestion; we do it in the silver layer so
bronze remains a complete audit copy. Tie-break is deterministic: lowest
`(received_ts, source_file, line_number)`. All duplicates in the sample are
exact payload copies, so the rule changes no metric — it only guarantees
reruns produce identical output. Dropped copies are kept in
`rejected_events` as `duplicate_event_id`.

## 5. Referential violations are rejected, not flagged

Events referencing unknown accounts/users, or inconsistent user/account
pairs, go to `rejected_events` instead of being kept with a warning flag.
Marts stay trivially clean and every dbt `relationships` test holds. Cost:
in production an "unknown account" is often metadata lag, not bad data — a
flag-and-keep policy would preserve those events for analysis. With 5
affected rows in this sample, explainability won over recall; the reverse
choice is defensible at scale (see docs/design.md).

## 6. Late events are kept, flagged, and dated by event_ts

`received_ts − event_ts > 1h` sets `is_late`; all date grouping uses
`event_ts` (when the user acted), never `received_ts` (when the pipeline
heard about it). A late-arriving event therefore lands on the day it
happened, which keeps daily metrics stable under reprocessing.

## 7. Missing cost is imputed, but never silently

9 of 138 AI calls lack `cost_usd`. Two columns coexist:
`cost_usd` (reported only) and `cost_usd_estimated` (reported, else
tokens × the model's observed cost-per-token), with `is_cost_estimated`
marking imputed rows. Finance can choose either total and always sees how
much of it is estimated ($1.85 known vs $1.98 estimated). Assumption
accepted: linear per-token pricing within this sample.

## 8. `sql/` and `dbt/` split — dbt owns transformations, sql/ owns the edges

`sql/create_tables.sql` is the bronze DDL executed by the Python loader
(dbt does not load external data); `sql/analytics/` holds read-only business
questions against gold (they materialize nothing, so they are not models).
Everything that turns one table into another lives in `dbt/models/`.

## 9. Event-name contract as a dbt seed

The list of valid `event_name` values was hardcoded in three places
(classification model, schema test, validate.py) — three edits to add an
event type, with silent drift if one is missed. It is now a seed
(`dbt/seeds/expected_event_names.csv`): the classification model reads it
via `ref()`, the schema test validates against it with a `relationships`
test, and validate.py queries the seeded table. One file to change, and the
change is reviewed like code. Seeds fit here precisely because this list is
small, static, analytics-owned reference data — unlike `accounts.csv` /
`users.csv`, which are operational source data and therefore enter through
ingestion (bronze, with file/timestamp lineage), never as seeds.
