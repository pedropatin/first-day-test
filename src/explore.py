"""Open the DuckDB UI in the browser to explore the pipeline database.

The database is attached read-only, so the UI can stay open while
`make run` or the dashboard write to the file. Uses the duckdb package
already in the venv — no DuckDB CLI install needed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"


def main() -> int:
    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run `make run` first.")
        return 1

    con = duckdb.connect()  # in-memory; UI state lives here, not in our file
    con.execute("INSTALL ui; LOAD ui;")
    con.execute(f"ATTACH '{DB_PATH}' AS firstday (READ_ONLY)")
    con.execute("USE firstday")
    print(con.execute("CALL start_ui()").fetchone()[0])
    print("Database attached read-only as 'firstday'. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
