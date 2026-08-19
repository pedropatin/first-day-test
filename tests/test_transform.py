"""Build the dbt models against the fixture dataset and check the outputs."""

import json
import os
import subprocess

import duckdb
import pytest

from conftest import REPO_ROOT
from ingest import run_ingest


@pytest.fixture(scope="module")
def built_db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("transform")
    raw = tmp / "raw"
    raw.mkdir()
    from conftest import ACCOUNTS_CSV, EVENT_LINES, USERS_CSV

    (raw / "events_2026-08-01.jsonl").write_text("\n".join(EVENT_LINES) + "\n")
    (raw / "accounts.csv").write_text(ACCOUNTS_CSV)
    (raw / "users.csv").write_text(USERS_CSV)

    db = tmp / "test.duckdb"
    run_ingest(raw, db)

    env = os.environ | {"FIRSTDAY_DB": str(db), "DBT_PROFILES_DIR": "."}
    result = subprocess.run(
        ["dbt", "build", "--no-use-colors"],
        cwd=REPO_ROOT / "dbt",
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return duckdb.connect(str(db), read_only=True)


def test_stg_events_keeps_only_valid_unique_events(built_db):
    ids = [r[0] for r in built_db.execute("select event_id from staging.stg_events").fetchall()]
    assert sorted(ids) == ["e01", "e02", "e03", "e04", "e05", "e06", "e07", "e08", "e09"]


def test_every_rejection_reason_is_assigned(built_db):
    reasons = dict(
        built_db.execute(
            "select coalesce(event_id, raw_data), rejection_reason from staging.rejected_events"
        ).fetchall()
    )
    assert reasons["e10"] == "unknown_event_name"
    assert reasons["e11"] == "missing_session_id"
    assert reasons["e12"] == "negative_metric_value"
    assert reasons["e13"] == "unknown_account"
    assert reasons["e14"] == "unknown_user"
    assert reasons["e15"] == "user_account_mismatch"
    assert reasons["e16"] == "unparseable_event_ts"
    assert reasons["e17"] == "invalid_property_type"
    assert reasons["e06"] == "duplicate_event_id"


def test_dedup_keeps_earliest_line(built_db):
    line, = built_db.execute(
        "select line_number from staging.stg_events where event_id = 'e06'"
    ).fetchone()
    dropped, = built_db.execute(
        "select line_number from staging.rejected_events where event_id = 'e06'"
    ).fetchone()
    assert line < dropped


def test_late_event_is_kept_and_flagged(built_db):
    is_late, event_date = built_db.execute(
        "select is_late, event_date from staging.stg_events where event_id = 'e08'"
    ).fetchone()
    assert is_late
    assert str(event_date) == "2026-08-01"  # dated by event_ts, not received_ts


def test_missing_cost_stays_null_but_gets_estimated(built_db):
    cost, estimated, is_estimated = built_db.execute(
        """select cost_usd, cost_usd_estimated, is_cost_estimated
           from marts.fact_ai_interactions where interaction_id = 'e07'"""
    ).fetchone()
    assert cost is None
    # e03 is the only costed m1 call: $0.01 / 120 tokens; e07 has 15 tokens
    assert estimated == pytest.approx(0.00125)
    assert is_estimated


def test_wrong_property_type_is_rejected_instead_of_becoming_null(built_db):
    reason, raw_data = built_db.execute(
        """select rejection_reason, raw_data
           from staging.rejected_events where event_id = 'e17'"""
    ).fetchone()
    assert reason == "invalid_property_type"
    assert json.loads(raw_data)["properties"]["latency_ms"] == "fast"


def test_session_funnel_flags(built_db):
    row = built_db.execute(
        """select has_session_started, has_prompt_submitted, has_ai_response,
                  has_response_accepted, has_workflow_completed, cost_usd
           from marts.fact_sessions where session_id = 's1'"""
    ).fetchone()
    assert row == (True, True, True, True, True, 0.01)


def test_daily_account_metrics_grain_and_counts(built_db):
    rows = built_db.execute(
        """select account_id, active_users, ai_interactions, ai_cost_usd,
                  uncosted_interactions
           from marts.daily_account_metrics order by account_id"""
    ).fetchall()
    # only acct_A has valid events; both users were active on 2026-08-01
    assert rows == [("acct_A", 2, 2, 0.01, 1)]


def test_row_count_reconciliation(built_db):
    raw, malformed, staged, rejected = built_db.execute(
        """select (select count(*) from raw.raw_events),
                  (select count(*) from raw.raw_ingest_rejections),
                  (select count(*) from staging.stg_events),
                  (select count(*) from staging.rejected_events)"""
    ).fetchone()
    assert raw + malformed == staged + rejected


def test_session_funnel_report_values(built_db):
    rows = built_db.execute(
        """select stage, sessions, pct_of_started
           from reports.rpt_session_funnel order by stage_order"""
    ).fetchall()
    assert rows == [
        ("session_started", 2, 100.0),
        ("prompt_submitted", 2, 100.0),
        ("ai_response_generated", 2, 100.0),
        ("response_accepted", 1, 50.0),
        ("workflow_completed", 1, 50.0),
    ]


def test_latency_report_values(built_db):
    row = built_db.execute(
        """select model, interactions, median_latency_ms, p95_latency_ms
           from reports.rpt_latency_by_model"""
    ).fetchone()
    assert row == ("m1", 2, 750.0, 975.0)


def test_daily_cost_report_values(built_db):
    reported, estimated, interactions, uncosted = built_db.execute(
        """select ai_cost_usd, ai_cost_usd_estimated,
                  ai_interactions, uncosted_interactions
           from reports.rpt_daily_cost_by_account
           where account_id = 'acct_A'"""
    ).fetchone()
    assert reported == pytest.approx(0.01)
    assert estimated == pytest.approx(0.0113)
    assert interactions == 2
    assert uncosted == 1
