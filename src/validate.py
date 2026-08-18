"""Post-build validation report.

dbt tests are the primary quality gate (run via `dbt build` / `make test`).
This script complements them with a human-readable report: row-count
reconciliation, a rejection breakdown, and cross-layer invariant checks.
It writes data/processed/validation_report.md and exits non-zero if any
check fails, so it works as a CI gate too.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"
DEFAULT_REPORT_PATH = REPO_ROOT / "data" / "processed" / "validation_report.md"


@dataclass
class Check:
    name: str
    sql: str  # must return a single count of VIOLATING rows (0 = pass)


CHECKS: list[Check] = [
    Check(
        "event_id unique in stg_events",
        "select count(*) from (select event_id from staging.stg_events group by 1 having count(*) > 1)",
    ),
    Check(
        "event_ts parsed and non-null in stg_events",
        "select count(*) from staging.stg_events where event_ts is null",
    ),
    Check(
        "required ids present in stg_events",
        """
        select count(*) from staging.stg_events
        where account_id is null or user_id is null
           or (session_id is null and event_name not in ('user_invited', 'user_signed_up'))
        """,
    ),
    Check(
        "event_name within expected values (from seed)",
        """
        select count(*) from staging.stg_events
        where event_name not in (select event_name from staging.expected_event_names)
        """,
    ),
    Check(
        "no negative tokens/latency/cost in stg_events",
        """
        select count(*) from staging.stg_events
        where least(coalesce(prompt_tokens,0), coalesce(completion_tokens,0),
                    coalesce(latency_ms,0), coalesce(cost_usd,0)) < 0
        """,
    ),
    Check(
        "all stg_events accounts exist in dim_accounts",
        """
        select count(*) from staging.stg_events e
        left join marts.dim_accounts a using (account_id) where a.account_id is null
        """,
    ),
    Check(
        "all stg_events users exist in dim_users",
        """
        select count(*) from staging.stg_events e
        left join marts.dim_users u using (user_id) where u.user_id is null
        """,
    ),
    Check(
        "row counts reconcile (raw + malformed = staged + rejected)",
        """
        select abs(
            (select count(*) from raw.raw_events)
            + (select count(*) from raw.raw_ingest_rejections)
            - (select count(*) from staging.stg_events)
            - (select count(*) from staging.rejected_events))
        """,
    ),
    Check(
        "every rejected row has a reason and lineage",
        """
        select count(*) from staging.rejected_events
        where rejection_reason is null or source_file is null or line_number is null
        """,
    ),
]


def run_report(db_path: Path, report_path: Path) -> bool:
    con = duckdb.connect(str(db_path), read_only=True)
    lines: list[str] = ["# Validation report", ""]

    lines.append("## Row counts")
    lines.append("")
    lines.append("| table | rows |")
    lines.append("|---|---:|")
    for table in (
        "raw.raw_events", "raw.raw_ingest_rejections",
        "raw.raw_accounts", "raw.raw_users",
        "staging.stg_events", "staging.rejected_events",
        "marts.dim_accounts", "marts.dim_users", "marts.fact_ai_interactions",
        "marts.fact_sessions", "marts.daily_account_metrics",
    ):
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        lines.append(f"| {table} | {n} |")

    lines.append("")
    lines.append("## Rejections by stage and reason")
    lines.append("")
    lines.append("| stage | reason | rows |")
    lines.append("|---|---|---:|")
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

    lines.append("")
    lines.append("## Checks")
    lines.append("")
    all_passed = True
    for check in CHECKS:
        violations = con.execute(check.sql).fetchone()[0]
        passed = violations == 0
        all_passed &= passed
        status = "PASS" if passed else f"FAIL ({violations} violations)"
        lines.append(f"- [{'x' if passed else ' '}] {check.name}: **{status}**")
        print(f"  {status:<6} {check.name}")

    con.close()
    report_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport written to {report_path}")
    return all_passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args(argv)

    print(f"Validating {args.db}")
    return 0 if run_report(args.db, args.report) else 1


if __name__ == "__main__":
    sys.exit(main())
