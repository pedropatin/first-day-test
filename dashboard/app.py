"""Streamlit dashboard over the mart tables. Run: make dashboard"""

from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "firstday.duckdb"

st.set_page_config(page_title="First Day — AI Usage", layout="wide")


@st.cache_data
def q(sql: str):
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(sql).df()


if not DB_PATH.exists():
    st.error("Database not found. Run `make run` first.")
    st.stop()

st.title("AI usage — 3-day sample")

# ---- KPIs -------------------------------------------------------------------
k = q("""
    select
        (select count(distinct user_id) from stg_events)            as users,
        (select count(*) from fact_sessions)                        as sessions,
        (select count(*) from fact_ai_interactions)                 as interactions,
        (select round(sum(ai_cost_usd_estimated), 2) from daily_account_metrics) as cost,
        (select round(100.0 * count(*) filter (has_workflow_completed)
                / count(*), 1) from fact_sessions where has_session_started) as completion
""").iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active users", int(k.users))
c2.metric("Sessions", int(k.sessions))
c3.metric("AI interactions", int(k.interactions))
c4.metric("Est. AI cost", f"${k.cost}")
c5.metric("Workflow completion", f"{k.completion}%")

tab_funnel, tab_cost, tab_models, tab_quality = st.tabs(
    ["Funnel", "Cost & usage", "Models", "Data quality"]
)

with tab_funnel:
    funnel = q("select stage, sessions from rpt_session_funnel order by stage_order")
    st.plotly_chart(
        px.funnel(funnel, x="sessions", y="stage"), use_container_width=True
    )

with tab_cost:
    left, right = st.columns(2)
    daily_cost = q("""
        select event_date, account_name, ai_cost_usd_estimated
        from daily_account_metrics order by event_date
    """)
    left.plotly_chart(
        px.bar(daily_cost, x="event_date", y="ai_cost_usd_estimated",
               color="account_name",
               title="Daily estimated AI cost by account"),
        use_container_width=True,
    )
    growth = q("""
        select event_date, account_name, events
        from daily_account_metrics order by event_date
    """)
    right.plotly_chart(
        px.line(growth, x="event_date", y="events", color="account_name",
                markers=True, title="Daily events by account"),
        use_container_width=True,
    )

with tab_models:
    left, right = st.columns(2)
    latency = q("""
        select model, median_latency_ms as median_ms, p95_latency_ms as p95_ms
        from rpt_latency_by_model order by median_ms
    """)
    left.plotly_chart(
        px.bar(latency.melt(id_vars="model", var_name="metric", value_name="ms"),
               x="model", y="ms", color="metric", barmode="group",
               title="Latency by model (median vs p95)"),
        use_container_width=True,
    )
    acceptance = q(
        "select model, acceptance_rate_pct from rpt_acceptance_by_model"
    )
    right.plotly_chart(
        px.bar(acceptance, x="model", y="acceptance_rate_pct",
               title="Acceptance rate by model (%)"),
        use_container_width=True,
    )
    st.dataframe(
        q("""
            select workflow, model, count(*) as interactions,
                   round(avg(total_tokens)) as avg_tokens,
                   round(sum(cost_usd_estimated), 4) as est_cost_usd
            from fact_ai_interactions group by all order by interactions desc
        """),
        use_container_width=True,
    )

with tab_quality:
    left, right = st.columns(2)
    reasons = q("""
        select case when rejection_reason like 'malformed_json%' then 'malformed_json'
                    else rejection_reason end as reason,
               count(*) as rows
        from rejected_events group by reason order by rows desc
    """)
    left.plotly_chart(
        px.bar(reasons, x="rows", y="reason", orientation="h",
               title="Rejected rows by reason"),
        use_container_width=True,
    )
    right.subheader("Rejected rows")
    right.dataframe(
        q("""
            select rejection_stage, rejection_reason, event_id,
                   source_file, line_number
            from rejected_events order by source_file, line_number
        """),
        use_container_width=True,
    )
