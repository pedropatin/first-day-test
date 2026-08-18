# First Day — Data Engineering Take-Home

Local pipeline: raw JSONL/CSV → DuckDB → dbt → a Streamlit dashboard.
One rule explains the whole repo: **`src/ingest.py` loads the raw files; dbt
does everything else.** Layers follow the dbt convention, carried by table
prefixes: `raw_*` → `stg_*` → `dim_*`/`fact_*` → `rpt_*`.

## Quickstart

Requires Python 3.10–3.13 and `make`.

```bash
make setup       # venv + pinned dependencies
make run         # ingest -> dbt build (models + 59 tests) -> validation report
make analytics   # print the answers to the 9 analytics questions
make test        # pytest (ingestion + transform on a fixture dataset)
make dashboard   # Streamlit dashboard at localhost:8501
make docs        # dbt lineage graph + table/column docs at localhost:8080
make explore     # browse every table in the DuckDB UI (read-only)
```

## How it works

```
data/raw/*.jsonl,*.csv
   │  src/ingest.py — parse only; keep every parseable line verbatim
   ▼
raw_events / raw_ingest_rejections / raw_accounts / raw_users
   │  dbt staging — type, flatten JSON, classify, dedup     (views)
   ▼
stg_events + rejected_events
   │  dbt marts — analyst-facing                            (tables)
   ▼
dim_accounts, dim_users, fact_ai_interactions, fact_sessions,
daily_account_metrics
   │  dbt marts/reports — the analytics questions           (views)
   ▼
rpt_daily_active_users ... rpt_acceptance_by_model  (one per question)
```

Everything after ingestion is one dbt DAG — run `make docs` to browse it as
an interactive lineage graph with every table and column described.

Design rule: **ingestion never drops or edits data**. Lines that fail JSON
parsing go to `raw_ingest_rejections`; everything else lands in `raw_events`
as-is (timestamps as strings). All judgment — casting, validation, dedup —
lives in dbt, where each rule is a readable SQL case and every rejected row
gets a reason. An invariant test guarantees no row is ever silently lost:

```
raw_events + raw_ingest_rejections == stg_events + rejected_events
```

### Layout

```
src/ingest.py                 load raw files into DuckDB (idempotent per file)
src/validate.py               human-readable report + reconciliation gate
src/run_analytics.py          prints the rpt_* views
src/explore.py                DuckDB UI over the database, read-only
sql/create_tables.sql         raw-layer DDL, executed by ingest.py
dbt/models/staging/           int_events_classified, stg_events, rejected_events
dbt/models/marts/             dims, facts, daily_account_metrics
dbt/models/marts/reports/     rpt_* — one view per analytics question
dbt/models/schema.yml         every table and column described + 59 tests
dbt/seeds/                    expected_event_names.csv — the event-name contract
tests/                        pytest: ingestion + full dbt build on a fixture dataset
dashboard/app.py              Streamlit, reads marts and rpt_* views
docs/design.md                production design note
docs/decisions.md             technical decision records (why, and what each accepts)
docs/ASSIGNMENT.md            original assignment
```

### Mapping to the assignment's expected deliverables

This project uses the assignment's Option B (dbt), so two expected files
exist in dbt form:

| assignment expects | here | why |
|---|---|---|
| `src/transform.py` | `dbt/models/` | transformations are versioned, tested SQL models instead of a script |
| `sql/marts.sql` | `dbt/models/marts/*.sql` | same marts, one file per model with its grain documented |
| analytics SQL queries | `dbt/models/marts/reports/rpt_*.sql` | each question is a view: uses ref(), tested, documented, in the lineage graph, and reused by the dashboard |
| `rejected_events` from ingestion | `raw_ingest_rejections` + `rejected_events` | parse failures captured at ingest; the staging model unions them with validation rejects so all rejections live in one queryable table |
| everything else | identical names and paths | — |

## Rejection rules

First failing rule wins; the row goes to `rejected_events` with that reason.

| order | reason | rule |
|---|---|---|
| 1 | `malformed_json` / `not_a_json_object` | line isn't a JSON object (ingest stage) |
| 2 | `missing_event_id` | no event_id |
| 3 | `unparseable_event_ts` | event_ts doesn't cast to timestamp |
| 4 | `unknown_event_name` | not one of the 9 expected names |
| 5 | `missing_account_id` / `missing_user_id` | always required |
| 6 | `missing_session_id` | required except `user_invited` / `user_signed_up` |
| 7 | `negative_metric_value` | tokens, latency, cost or duration < 0 |
| 8 | `unknown_account` / `unknown_user` / `user_account_mismatch` | fails referential check against metadata |
| 9 | `duplicate_event_id` | later copy of an already-kept event |

**Dedup tie-break:** first received wins — lowest `(received_ts, source_file,
line_number)`. All duplicates in this sample are exact payload copies, so
which copy wins doesn't change any metric; the rule just makes it deterministic.

**Late events** (received_ts − event_ts > 1h) are kept and flagged `is_late`,
and always count on the day of `event_ts`.

On this sample: 725 input lines → 690 clean events + 35 rejected
(6 malformed, 12 duplicates, 6 unknown event names, 3 negative metrics,
5 bad references, 3 missing/invalid required fields). Full breakdown in
`data/processed/validation_report.md` after `make run`.

## Models and grains

| model | grain |
|---|---|
| `stg_events` | one row per unique valid event |
| `rejected_events` | one row per rejected line/event, with stage + reason + file/line |
| `dim_accounts` / `dim_users` | one row per account / user (emails masked to domain) |
| `fact_ai_interactions` | one row per `ai_response_generated` event, with known + estimated cost |
| `fact_sessions` | one row per session, with funnel flags and totals |
| `daily_account_metrics` | one row per (event_date, account_id) |

## Metric definitions worth stating

- **Active user** = distinct user with ≥1 valid event that day.
- **AI cost** comes in two columns: `ai_cost_usd` sums only *reported*
  `cost_usd`; `ai_cost_usd_estimated` imputes the 9 (of 138) missing costs as
  tokens × the model's observed cost-per-token, with `is_cost_estimated`
  marking imputed rows. Known total $1.85, estimated total $1.98.
- **Funnel** = share of started sessions where each stage *ever* happened,
  cumulatively (a stage only counts if all previous stages happened too).
- **Rejection rate (Q6)** = rejected / (accepted + rejected) explicit
  decisions, not / all AI responses — most responses get no decision event.
- **Unusual error rate (Q7)** = above mean + 2σ of per-user rates, min 10 events.
- **Growth (Q8)** = day-3 vs day-1 events. Three days is direction, not a trend.

## What the data says

- **Funnel converts 55.7%** of started sessions into completed workflows; the
  biggest single drop is response acceptance (87.3% → 67.7%).
- **`gpt-5.5-mini` matches `gpt-5.5` on acceptance (75.6% vs 75.9%) at ~1/4
  the cost per call and 2.5× the speed** (median 1.2s vs 3.0s) — the routing
  decision the data argues for. `gpt-4.1` has the highest acceptance (84%)
  but on only 25 flagged calls.
- **Atlas Legal (acct_004) is a churn-risk signal**: highest rejection rate
  (38.5%), usage down 50% over the sample, and the only user flagged for
  unusual error rate (user_019) — worth a proactive check-in.
- **Orbit People (acct_006) grew 178%** in three days; Cedar Finance
  (acct_005) is the largest account by volume and cost (~$0.49 of $1.85 total).

## Submission notes

- **Time spent:** ~6 hours.
- **Prioritized:** correctness of the raw→rejected→staged accounting, explicit
  rejection reasons, dbt tests on every model, deterministic reruns.
- **With more time:** incremental loading (currently full-refresh per file),
  CI, seat-limit utilization vs `seat_limit`, unit economics (cost per
  accepted response), a cost anomaly check, richer session ordering in the
  funnel (strict stage sequence by timestamp).
- **AI tools:** built with Claude Code. Verified by profiling the raw data
  independently before writing any transform, reconciling every pipeline count
  against that profile (725 = 690 + 35), the pytest suite over a hand-built
  fixture covering each issue class, and 59 dbt tests.
