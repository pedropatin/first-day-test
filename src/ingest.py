"""Ingest raw JSONL event files and CSV metadata into DuckDB.

Responsibilities of this layer (and nothing more):
  * parse each JSONL line; keep every parseable event object in `raw_events`
    verbatim (no casting, no dedup — that happens in dbt staging);
  * capture unparseable lines in `raw_ingest_rejections` with lineage
    (source file, line number, raw text, reason);
  * load `accounts.csv` / `users.csv` into `raw_accounts` / `raw_users`.

Idempotency: each run replaces the rows belonging to the files it ingests
(delete-by-source_file + insert), so re-running never duplicates data.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"
CREATE_TABLES_SQL = REPO_ROOT / "sql" / "create_tables.sql"

# Top-level keys promoted to columns; anything else stays in raw_payload.
EVENT_COLUMNS = (
    "event_id",
    "event_ts",
    "received_ts",
    "account_id",
    "user_id",
    "session_id",
    "event_name",
)


@dataclass
class IngestStats:
    events_loaded: int = 0
    lines_rejected: int = 0
    accounts_loaded: int = 0
    users_loaded: int = 0


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(CREATE_TABLES_SQL.read_text())
    return con


def _parse_line(line: str) -> tuple[dict | None, str | None]:
    """Return (event_object, None) or (None, rejection_reason)."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        return None, f"malformed_json: {exc.msg} (char {exc.pos})"
    if not isinstance(obj, dict):
        return None, f"not_a_json_object: got {type(obj).__name__}"
    return obj, None


def ingest_events_file(
    con: duckdb.DuckDBPyConnection, path: Path, ingested_at: datetime
) -> tuple[int, int]:
    """Load one JSONL file. Returns (rows_loaded, rows_rejected)."""
    source_file = path.name
    events: list[tuple] = []
    rejections: list[tuple] = []

    with path.open() as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            obj, reason = _parse_line(line)
            if obj is None:
                rejections.append(
                    (source_file, line_number, line, reason, ingested_at)
                )
                continue
            row = [obj.get(col) for col in EVENT_COLUMNS]
            properties = obj.get("properties")
            events.append(
                (
                    *row,
                    json.dumps(properties) if properties is not None else None,
                    json.dumps(obj),
                    source_file,
                    line_number,
                    ingested_at,
                )
            )

    # Replace this file's rows so re-runs are idempotent.
    con.execute("DELETE FROM bronze.raw_events WHERE source_file = ?", [source_file])
    con.execute(
        "DELETE FROM bronze.raw_ingest_rejections WHERE source_file = ?", [source_file]
    )
    if events:
        con.executemany(
            "INSERT INTO bronze.raw_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            events,
        )
    if rejections:
        con.executemany(
            "INSERT INTO bronze.raw_ingest_rejections VALUES (?, ?, ?, ?, ?)", rejections
        )
    return len(events), len(rejections)


def ingest_csv(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    table: str,
    ingested_at: datetime,
) -> int:
    """Load a metadata CSV, replacing the table contents."""
    con.execute(f"DELETE FROM {table} WHERE source_file = ?", [path.name])
    con.execute(
        f"""
        INSERT INTO {table}
        SELECT *, ? AS source_file, ? AS ingested_at
        FROM read_csv(?, header = true)
        """,
        [path.name, ingested_at, str(path)],
    )
    return con.execute(
        f"SELECT count(*) FROM {table} WHERE source_file = ?", [path.name]
    ).fetchone()[0]


def run_ingest(raw_dir: Path, db_path: Path) -> IngestStats:
    con = connect(db_path)
    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    stats = IngestStats()

    event_files = sorted(raw_dir.glob("events_*.jsonl"))
    if not event_files:
        raise FileNotFoundError(f"no events_*.jsonl files found in {raw_dir}")

    for path in event_files:
        loaded, rejected = ingest_events_file(con, path, ingested_at)
        stats.events_loaded += loaded
        stats.lines_rejected += rejected
        print(f"  {path.name}: {loaded} events, {rejected} rejected lines")

    stats.accounts_loaded = ingest_csv(
        con, raw_dir / "accounts.csv", "bronze.raw_accounts", ingested_at
    )
    stats.users_loaded = ingest_csv(
        con, raw_dir / "users.csv", "bronze.raw_users", ingested_at
    )
    print(f"  accounts.csv: {stats.accounts_loaded} rows")
    print(f"  users.csv: {stats.users_loaded} rows")

    con.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args(argv)

    print(f"Ingesting {args.raw_dir} -> {args.db}")
    stats = run_ingest(args.raw_dir, args.db)
    print(
        f"Done: {stats.events_loaded} events, {stats.lines_rejected} rejected lines, "
        f"{stats.accounts_loaded} accounts, {stats.users_loaded} users."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
