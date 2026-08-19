"""Shared fixture: a small raw dataset covering every issue class."""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

ACCOUNTS_CSV = """account_id,account_name,plan,industry,seat_limit,created_at
acct_A,Acme,pro,tech,10,2026-01-01T00:00:00Z
acct_B,Beta,starter,retail,5,2026-02-01T00:00:00Z
"""

USERS_CSV = """user_id,account_id,email,role,status,created_at
user_1,acct_A,u1@acme.example,admin,active,2026-03-01T00:00:00Z
user_2,acct_A,u2@acme.example,member,active,2026-03-02T00:00:00Z
user_3,acct_B,u3@beta.example,admin,active,2026-03-03T00:00:00Z
"""


def _evt(event_id, name, ts="2026-08-01T10:00:00Z", account="acct_A",
         user="user_1", session="s1", received=None, props=None, **overrides):
    obj = {
        "event_id": event_id,
        "event_ts": ts,
        "received_ts": received or ts,
        "account_id": account,
        "user_id": user,
        "session_id": session,
        "event_name": name,
        "properties": props or {},
    }
    obj.update(overrides)
    return json.dumps({k: v for k, v in obj.items() if v is not None})


# One clean full-funnel session, plus one row per known data issue.
EVENT_LINES = [
    _evt("e01", "session_started", "2026-08-01T10:00:00Z", props={"workflow": "onboarding", "device": "web"}),
    _evt("e02", "prompt_submitted", "2026-08-01T10:01:00Z", props={"workflow": "onboarding", "prompt_length_chars": 50}),
    _evt("e03", "ai_response_generated", "2026-08-01T10:02:00Z",
         props={"model": "m1", "prompt_tokens": 100, "completion_tokens": 20,
                "latency_ms": 1000, "cost_usd": 0.01, "workflow": "onboarding", "accepted": True}),
    _evt("e04", "response_accepted", "2026-08-01T10:03:00Z", props={"workflow": "onboarding"}),
    _evt("e05", "workflow_completed", "2026-08-01T10:04:00Z", props={"workflow": "onboarding", "duration_ms": 240000}),
    # duplicate pair: same event_id and received_ts; earlier line must win
    _evt("e06", "session_started", "2026-08-01T11:00:00Z", user="user_2", session="s2"),
    _evt("e06", "session_started", "2026-08-01T11:00:00Z", user="user_2", session="s2"),
    # ai response with missing cost_usd: kept, cost stays NULL
    _evt("e07", "ai_response_generated", "2026-08-01T11:05:00Z", user="user_2", session="s2",
         props={"model": "m1", "prompt_tokens": 10, "completion_tokens": 5, "latency_ms": 500, "workflow": "onboarding"}),
    # late arrival (>1h): kept, flagged
    _evt("e08", "prompt_submitted", "2026-08-01T12:00:00Z", user="user_2", session="s2",
         received="2026-08-03T12:00:00Z", props={"workflow": "onboarding", "prompt_length_chars": 10}),
    # signup without session_id: allowed
    _evt("e09", "user_signed_up", "2026-08-01T09:00:00Z", session=None, props={"invite_channel": "email"}),
    # rejects, one per staging rule
    _evt("e10", "totally_unknown_event"),
    _evt("e11", "prompt_submitted", session=None, props={"workflow": "onboarding"}),
    _evt("e12", "ai_response_generated", props={"model": "m1", "latency_ms": -5}),
    _evt("e13", "session_started", account="acct_X"),
    _evt("e14", "session_started", user="user_9"),
    _evt("e15", "session_started", user="user_3"),  # user_3 belongs to acct_B
    _evt("e16", "session_started", ts="2026-08-01 99:99:99"),
    _evt("e17", "ai_response_generated",
         props={"model": "m1", "latency_ms": "fast"}),
    _evt(None, "session_started"),
    # ingest-level rejects
    "{not valid json",
    '["an", "array"]',
]


@pytest.fixture
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    (d / "events_2026-08-01.jsonl").write_text("\n".join(EVENT_LINES) + "\n")
    (d / "accounts.csv").write_text(ACCOUNTS_CSV)
    (d / "users.csv").write_text(USERS_CSV)
    return d


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.duckdb"
