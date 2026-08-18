"""Post-build validation report.

Quality checks live in one place: the dbt tests, which run inside
`dbt build` and fail it on violation. This script does not re-test — it
produces the human-readable summary (row counts per table, rejection
breakdown by stage and reason) and enforces the one cross-layer invariant
that spans tables dbt builds separately:

    raw_events + raw_ingest_rejections == stg_events + rejected_events

It writes data/processed/validation_report.md and exits non-zero if the
invariant breaks, so it also works as a CI gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"
DEFAULT_REPORT_PATH = REPO_ROOT / "data" / "processed" / "validation_report.md"

TABLES = (
    "raw.raw_events", "raw.raw_ingest_rejections", "raw.raw_accounts",
    "raw.raw_users", "staging.stg_events", "staging.rejected_events",
    "marts.dim_accounts", "marts.dim_users", "marts.fact_ai_interactions",
    "marts.fact_sessions", "marts.daily_account_metrics",
)


def run_report(db_path: Path, report_path: Path) -> bool:
    con = duckdb.connect(str(db_path), read_only=True)
    lines: list[str] = ["# Validation report", "", "## Row counts", ""]

    lines += ["| table | rows |", "|---|---:|"]
    for table in TABLES:
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        lines.append(f"| {table} | {n} |")

    lines += ["", "## Rejections by stage and reason", ""]
    lines += ["| stage | reason | rows |", "|---|---|---:|"]
    for stage, reason, n in con.execute(
        """
        select rejection_stage,
               -- collapse per-line json parser detail into one bucket
               case when rejection_reason like 'malformed_json%' then 'malformed_json'
                    else rejection_reason end as reason,
               count(*)
        from staging.rejected_events group by 1, 2 order by 1, 3 desc
        """
    ).fetchall():
        lines.append(f"| {stage} | {reason} | {n} |")

    raw, malformed, staged, rejected = con.execute(
        """
        select (select count(*) from raw.raw_events),
               (select count(*) from raw.raw_ingest_rejections),
               (select count(*) from staging.stg_events),
               (select count(*) from staging.rejected_events)
        """
    ).fetchone()
    con.close()

    reconciled = raw + malformed == staged + rejected
    status = "PASS" if reconciled else "FAIL"
    lines += [
        "",
        "## Reconciliation",
        "",
        f"- raw_events ({raw}) + malformed lines ({malformed}) "
        f"= stg_events ({staged}) + rejected_events ({rejected}): **{status}**",
        "",
        "Quality checks (uniqueness, references, value ranges) run as dbt "
        "tests inside `dbt build`.",
    ]
    print(f"  {status}  reconciliation: {raw} + {malformed} = {staged} + {rejected}")

    report_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to {report_path}")
    return reconciled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)

    print(f"Validating {args.db}")
    return 0 if run_report(args.db, args.report) else 1


if __name__ == "__main__":
    sys.exit(main())
