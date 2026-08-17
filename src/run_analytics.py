"""Execute the analytics queries in sql/analytics/ and print the results.

Each .sql file is one business question; the leading comment block in the
file states the metric definition and its assumptions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"
ANALYTICS_DIR = REPO_ROOT / "sql" / "analytics"


def run_query_file(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    sql = path.read_text()
    header = next(
        (line.lstrip("- ").strip() for line in sql.splitlines() if line.startswith("--")),
        path.stem,
    )
    print(f"\n{'=' * 78}\n{header}  [{path.name}]\n{'=' * 78}")
    df = con.execute(sql).df()
    print(df.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--only", help="run a single query by file-name prefix, e.g. q5"
    )
    args = parser.parse_args(argv)

    files = sorted(ANALYTICS_DIR.glob("*.sql"))
    if args.only:
        files = [f for f in files if f.name.startswith(args.only)]
    if not files:
        print("no analytics queries found", file=sys.stderr)
        return 1

    con = duckdb.connect(str(args.db), read_only=True)
    for path in files:
        run_query_file(con, path)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
