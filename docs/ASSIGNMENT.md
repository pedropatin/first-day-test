# First Day Data Engineer Take-Home Assignment

## Repository

- [Assignment repository](https://github.com/first-day-life/firstday-data-engineering-takehome)
- [Provided raw input data](https://github.com/first-day-life/firstday-data-engineering-takehome/tree/main/data/raw)

Clone the repository to begin:

```bash
git clone https://github.com/first-day-life/firstday-data-engineering-takehome.git
cd firstday-data-engineering-takehome
```

## Time expectation

Please spend **4–8 focused hours** on this assignment. We care more about clear tradeoffs, correctness, and maintainability than about building a large system.

In your submission, tell us:

- How much time you spent.
- What you prioritized.
- What you would improve with more time.
- Any AI tools you used and how you verified their output.

## Background

First Day builds AI-powered workflows. A core data engineering responsibility is turning raw product and AI-interaction events into trustworthy datasets for product, operations, finance, and leadership.

You are given raw event files that simulate product usage, AI model calls, feedback, and account metadata. Your task is to build a small local data pipeline that ingests, validates, models, and exposes analytics-ready tables.

The assignment should run locally. Do not use paid cloud resources or real API keys.

> **Synthetic data notice:** Every account, user, email address, identifier, timestamp, event, model interaction, token count, latency, and cost in this repository is fictional and programmatically generated for this exercise. The dataset contains no First Day customer, employee, applicant, production, or internal operational data, and no data belonging to the assignment author. Email addresses use the reserved `.example` domain. Any resemblance to a real person or organization is coincidental.

## Input data

The repository contains:

```text
data/raw/events_2026-08-01.jsonl
data/raw/events_2026-08-02.jsonl
data/raw/events_2026-08-03.jsonl
data/raw/accounts.csv
data/raw/users.csv
```

You can also inspect the supplied inputs directly on GitHub:

- [`events_2026-08-01.jsonl`](https://github.com/first-day-life/firstday-data-engineering-takehome/blob/main/data/raw/events_2026-08-01.jsonl)
- [`events_2026-08-02.jsonl`](https://github.com/first-day-life/firstday-data-engineering-takehome/blob/main/data/raw/events_2026-08-02.jsonl)
- [`events_2026-08-03.jsonl`](https://github.com/first-day-life/firstday-data-engineering-takehome/blob/main/data/raw/events_2026-08-03.jsonl)
- [`accounts.csv`](https://github.com/first-day-life/firstday-data-engineering-takehome/blob/main/data/raw/accounts.csv)
- [`users.csv`](https://github.com/first-day-life/firstday-data-engineering-takehome/blob/main/data/raw/users.csv)

Each line in an event file is intended to represent a JSON object with this shape:

```json
{
  "event_id": "evt_123",
  "event_ts": "2026-08-01T09:31:22Z",
  "received_ts": "2026-08-01T09:31:25Z",
  "account_id": "acct_001",
  "user_id": "user_001",
  "session_id": "sess_001",
  "event_name": "ai_response_generated",
  "properties": {
    "model": "gpt-5.5",
    "prompt_tokens": 814,
    "completion_tokens": 241,
    "latency_ms": 3120,
    "cost_usd": 0.018,
    "workflow": "onboarding",
    "accepted": true
  }
}
```

Expected `event_name` values are:

```text
user_invited
user_signed_up
session_started
prompt_submitted
ai_response_generated
response_accepted
response_rejected
workflow_completed
error_raised
```

### Known data issues

Your pipeline should handle these issue classes:

- Duplicate `event_id` values.
- Late-arriving events where `received_ts` is much later than `event_ts`.
- Missing optional fields inside `properties`.
- Malformed or nonconforming JSON lines.
- Unknown `event_name` values.
- Events that reference users or accounts not found in the metadata files, or inconsistent user/account pairs.
- Invalid values that should be surfaced by data-quality checks.
- Multiple model names and workflows.

The list describes issue classes, not an exhaustive row-level answer key.

## Your task

Build a local data pipeline that produces trustworthy, analytics-ready data.

You may use any reasonable stack. Suggested options are:

```text
Option A: Python + DuckDB + SQL
Option B: Python + DuckDB + dbt
Option C: Python + Postgres + SQL
```

Avoid heavy infrastructure unless it clearly improves your solution. Airflow, Kafka, Spark, and cloud services are not required.

## Required deliverables

Your submission should include the equivalent of:

```text
README.md
src/
  ingest.py
  transform.py
  validate.py
sql/
  create_tables.sql
  marts.sql
tests/
  test_ingest.py
  test_transform.py
data/
  raw/
  processed/
docs/
  design.md
```

The exact structure may differ, but a reviewer should be able to understand and run the project without guessing.

## Pipeline requirements

### 1. Ingestion

Load the raw JSONL and CSV files into a local analytical database.

Your ingestion should:

- Preserve raw events in a raw table.
- Capture malformed or rejected rows in a rejected-events table.
- Deduplicate events using `event_id` and document your tie-breaking rule.
- Keep enough lineage to debug ingestion, such as source file, load timestamp, and rejection reason.

Expected output tables:

```text
raw_events
rejected_events
raw_accounts
raw_users
```

### 2. Validation

Add basic data-quality checks. At minimum, validate that:

- `event_id` is present and unique in the cleaned event table.
- `event_ts` is parseable.
- `account_id`, `user_id`, and `session_id` are present where required.
- `event_name` is one of the expected values.
- Token counts, latency, and cost are non-negative when present.
- Account and user references are valid where possible.

Validation may use Python tests, SQL checks, dbt tests, or a small custom validation report. Make rejected or failing records explainable.

### 3. Modeling

Create clean staging tables and analytics marts.

Minimum expected tables:

```text
stg_events
dim_accounts
dim_users
fact_ai_interactions
fact_sessions
daily_account_metrics
```

Document the grain and important assumptions for each model. The marts should answer product and business questions without requiring analysts to re-parse raw JSON.

### 4. Analytics questions

Include SQL queries that answer:

1. Daily active users by account.
2. Number of AI interactions by workflow and model.
3. Median and p95 latency by model.
4. Daily estimated AI cost by account.
5. Session conversion funnel:
   - session started
   - prompt submitted
   - AI response generated
   - response accepted
   - workflow completed
6. Top accounts by rejected responses.
7. Users with unusually high error rates.
8. Accounts with usage growth over the three-day sample.

State any metric definitions or assumptions that could reasonably be interpreted more than one way.

### 5. Production design note

In `docs/design.md`, explain how you would evolve this into a production pipeline. Cover:

- Batch versus streaming ingestion.
- Schema evolution.
- Data quality and alerting.
- Backfills and idempotency.
- Personally identifiable information handling.
- Cost monitoring.
- How you would expose the data to analysts or internal tools.
- What you intentionally skipped because of the 8–10 hour limit.

## How we will run it

Provide one command or a small, clearly documented set of commands, for example:

```bash
make setup
make run
make test
```

or:

```bash
docker compose up --build
```

The reviewer should be able to run the project locally from a clean checkout without hidden steps.

## Evaluation rubric

| Area | Weight | What strong looks like |
|---|---:|---|
| Correctness | 25% | Handles malformed rows, duplicates, missing fields, and produces correct metrics. |
| Data modeling | 20% | Clear grains, sensible facts and dimensions, thoughtful JSON flattening, and analyst-friendly marts. |
| Code quality | 20% | Modular and readable code, typed where useful, with simple abstractions and no unnecessary complexity. |
| Reproducibility | 15% | Clear instructions, pinned dependencies, a simple run path, and deterministic outputs. |
| Data quality | 10% | Meaningful checks, explainable rejected records, and tests covering important edge cases. |
| Product thinking | 10% | Useful metrics and a design note that explains tradeoffs and a credible production path. |

## Optional stretch goals

Only attempt these after the core assignment works:

- Add dbt models and dbt tests.
- Add a small dashboard or notebook.
- Add GitHub Actions for tests.
- Add incremental loading.
- Add a simple cost anomaly detector.
- Add generated documentation for final tables.

## What not to spend time on

- Paid cloud infrastructure.
- Complex orchestration before the core pipeline works.
- A highly polished dashboard at the expense of correctness.
- Large frameworks that make the project difficult to run locally.

We prefer a small, reliable, well-explained pipeline over an ambitious but fragile one.
