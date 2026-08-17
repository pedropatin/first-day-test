"""Build the dbt models against the fixture dataset and check the outputs."""

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
    ids = [r[0] for r in built_db.execute("select event_id from stg_events").fetchall()]
    assert sorted(ids) == ["e01", "e02", "e03", "e04", "e05", "e06", "e07", "e08", "e09"]


def test_every_rejection_reason_is_assigned(built_db):
    reasons = dict(
        built_db.execute(
            "select coalesce(event_id, raw_data), rejection_reason from rejected_events"
        ).fetchall()
    )
    assert reasons["e10"] == "unknown_event_name"
    assert reasons["e11"] == "missing_session_id"
    assert reasons["e12"] == "negative_metric_value"
    assert reasons["e13"] == "unknown_account"
    assert reasons["e14"] == "unknown_user"
    assert reasons["e15"] == "user_account_mismatch"
    assert reasons["e16"] == "unparseable_event_ts"
    assert reasons["e06"] == "duplicate_event_id"


def test_dedup_keeps_earliest_line(built_db):
    line, = built_db.execute(
        "select line_number from stg_events where event_id = 'e06'"
    ).fetchone()
    dropped, = built_db.execute(
        "select line_number from rejected_events where event_id = 'e06'"
    ).fetchone()
    assert line < dropped


def test_late_event_is_kept_and_flagged(built_db):
    is_late, event_date = built_db.execute(
        "select is_late, event_date from stg_events where event_id = 'e08'"
    ).fetchone()
    assert is_late
    assert str(event_date) == "2026-08-01"  # dated by event_ts, not received_ts


def test_missing_cost_stays_null(built_db):
    cost, = built_db.execute(
        "select cost_usd from fact_ai_interactions where interaction_id = 'e07'"
    ).fetchone()
    assert cost is None


def test_session_funnel_flags(built_db):
    row = built_db.execute(
        """select has_session_started, has_prompt_submitted, has_ai_response,
                  has_response_accepted, has_workflow_completed, cost_usd
           from fact_sessions where session_id = 's1'"""
    ).fetchone()
    assert row == (True, True, True, True, True, 0.01)


def test_daily_account_metrics_grain_and_counts(built_db):
    rows = built_db.execute(
        """select account_id, active_users, ai_interactions, ai_cost_usd,
                  uncosted_interactions
           from daily_account_metrics order by account_id"""
    ).fetchall()
    # only acct_A has valid events; both users were active on 2026-08-01
    assert rows == [("acct_A", 2, 2, 0.01, 1)]


def test_row_count_reconciliation(built_db):
    raw, malformed, staged, rejected = built_db.execute(
        """select (select count(*) from raw_events),
                  (select count(*) from raw_ingest_rejections),
                  (select count(*) from stg_events),
                  (select count(*) from rejected_events)"""
    ).fetchone()
    assert raw + malformed == staged + rejected
