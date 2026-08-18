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
explicit reason. Cost: the raw layer stores some garbage by design — that
is what a raw layer is for.

## 3. One schema; table prefixes carry the layer

This evolved twice. A first version used medallion schemas
(`bronze`/`silver`/`gold`) — dropped because it duplicated in the schema
name what the dbt-convention table prefixes (`raw_`, `stg_`, `dim_`/`fact_`)
already say, and forced every query to carry a translation
(`silver.stg_events`). A second version kept dbt-named schemas
(`raw`/`staging`/`marts`) — still redundant (`staging.stg_events`). Final
form: one schema, prefixes carry the layer, every reference is short
(`from stg_events`). Physical schema separation buys access control, which
matters in a warehouse and not in a local DuckDB file; docs/design.md covers
the production version. Staging and report models are views (rules, not
state); core marts are tables.

## 4. Deduplication in staging, not ingestion; first-received wins

The assignment places dedup under ingestion; we do it in staging so the
raw layer remains a complete audit copy. Tie-break is deterministic: lowest
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

## 8. Ingestion is the only non-dbt SQL

`sql/create_tables.sql` is the raw-layer DDL executed by the Python loader —
it cannot be a dbt model because dbt does not load external data. Everything
else is dbt. (An earlier version also kept the analytics questions in
`sql/analytics/`; see decision 10 for why they moved into dbt.)

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
ingestion (the raw layer, with file/timestamp lineage), never as seeds.

## 10. Analytics questions as dbt report views

The 9 analytics questions started as loose SQL files in `sql/analytics/`.
That made them second-class citizens: raw table names instead of `ref()`
(every schema change meant editing all 9 files), invisible in the lineage
graph, untestable, and the dashboard re-implemented the same logic a third
time. They are now views in `dbt/models/marts/reports/` (`rpt_*`) — a
subfolder of marts, keeping the official staging/marts structure intact
rather than inventing a top-level layer. Each question uses `ref()`, appears
in `dbt docs`, is described in schema.yml, and the dashboard reads the same
views, so every metric has exactly one definition. `dbt/analyses/` was
considered and rejected: analyses compile but don't materialize, which would
have kept the dashboard duplication alive.

## 11. Quality checks live only in dbt tests

`validate.py` originally re-implemented seven checks that dbt tests already
enforced — two sources of truth that could drift. It is now report-only
(row counts, rejection breakdown) plus the single cross-layer invariant
(`raw + malformed = staged + rejected`) as its exit-code gate. Every other
check exists exactly once, as a dbt test that fails the build.

## 12. Every table and column described in schema.yml

All models, sources, and the seed carry descriptions, browsable via
`make docs` (dbt lineage graph + catalog). The grain of each model is also
stated as a comment at the top of its SQL file, where a code reader will
see it without opening the docs site.
