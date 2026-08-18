"""Print the answers to the analytics questions.

Each question is a dbt view in dbt/models/marts/reports/ — the metric
definition and its assumptions live in that model's SQL and schema.yml.
This script just selects and prints them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "processed" / "firstday.duckdb"

REPORTS = [
    ("Q1", "rpt_daily_active_users", "Daily active users by account"),
    ("Q2", "rpt_ai_interactions_by_workflow_model", "AI interactions by workflow and model"),
    ("Q3", "rpt_latency_by_model", "Median and p95 latency by model"),
    ("Q4", "rpt_daily_cost_by_account", "Daily estimated AI cost by account"),
    ("Q5", "rpt_session_funnel", "Session conversion funnel"),
    ("Q6", "rpt_rejected_responses_by_account", "Top accounts by rejected responses"),
    ("Q7", "rpt_high_error_rate_users", "Users with unusually high error rates"),
    ("Q8", "rpt_account_usage_growth", "Account usage growth over the sample"),
    ("Q9", "rpt_acceptance_by_model", "Acceptance rate by model (extra)"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--only", help="run a single question, e.g. Q5 or q5")
    args = parser.parse_args(argv)

    reports = REPORTS
    if args.only:
        reports = [r for r in REPORTS if r[0].lower() == args.only.lower()]
        if not reports:
            print(f"unknown question {args.only!r}", file=sys.stderr)
            return 1

    con = duckdb.connect(str(args.db), read_only=True)
    for number, view, title in reports:
        print(f"\n{'=' * 78}\n{number}. {title}  [{view}]\n{'=' * 78}")
        print(con.execute(f"select * from reports.{view}").df().to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
