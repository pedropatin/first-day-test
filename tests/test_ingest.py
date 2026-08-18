import duckdb

from ingest import run_ingest


def test_loads_all_parseable_events(raw_dir, db_path):
    stats = run_ingest(raw_dir, db_path)
    assert stats.events_loaded == 18  # 20 lines - 2 unparseable
    assert stats.lines_rejected == 2
    assert stats.accounts_loaded == 2
    assert stats.users_loaded == 3


def test_rejections_keep_lineage(raw_dir, db_path):
    run_ingest(raw_dir, db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    rows = con.execute(
        "select source_file, line_number, raw_line, rejection_reason "
        "from raw.raw_ingest_rejections order by line_number"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][2] == "{not valid json"
    assert rows[0][3].startswith("malformed_json")
    assert rows[1][3] == "not_a_json_object: got list"
    assert all(r[0] == "events_2026-08-01.jsonl" and r[1] > 0 for r in rows)


def test_reingest_is_idempotent(raw_dir, db_path):
    run_ingest(raw_dir, db_path)
    run_ingest(raw_dir, db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    assert con.execute("select count(*) from raw.raw_events").fetchone()[0] == 18
    assert con.execute("select count(*) from raw.raw_ingest_rejections").fetchone()[0] == 2
    assert con.execute("select count(*) from raw.raw_accounts").fetchone()[0] == 2


def test_raw_preserves_original_payload(raw_dir, db_path):
    run_ingest(raw_dir, db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    ts, payload = con.execute(
        "select event_ts, raw_payload from raw.raw_events where event_id = 'e16'"
    ).fetchone()
    assert ts == "2026-08-01 99:99:99"  # kept verbatim; staging rejects it
    assert "99:99:99" in payload
