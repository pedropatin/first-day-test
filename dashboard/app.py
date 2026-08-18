"""Streamlit dashboard over the mart tables, in First Day's visual identity.

Brand: blue #486CED, ink #2C3D50, light surface #F2FBFF (firstday.com);
Fraunces for titles, Poppins for body. Chart palette derived from the brand
hues and validated for colorblind safety (fixed order, color follows the
account). Run: make dashboard
"""

from pathlib import Path

import duckdb
import plotly.express as px
import plotly.io as pio
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
DB_PATH = REPO / "data" / "processed" / "firstday.duckdb"
LOGO = str(REPO / "dashboard" / "assets" / "firstday_logo.png")

BLUE, INK, SURFACE = "#486CED", "#2C3D50", "#F2FBFF"
# Validated categorical palette (fixed order — color follows the account).
CATEGORICAL = ["#486CED", "#D98E00", "#1F9BB8", "#E0577C",
               "#8A5BE0", "#12714C", "#C94F9E", "#7A8B21"]

st.set_page_config(page_title="First Day — AI Usage", page_icon=LOGO, layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Poppins:wght@400;500;600&display=swap');
html, body, [class*="css"], p, div, span, label { font-family: 'Poppins', sans-serif; }
h1, h2, h3 { font-family: 'Fraunces', serif !important; color: #2C3D50; }
h1 { font-weight: 600; }
[data-testid="stMetric"] {
    background: #F2FBFF; border: 1px solid #E1EFFB;
    border-radius: 16px; padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-family: 'Fraunces', serif; color: #486CED; }
[data-testid="stMetricLabel"] { color: #2C3D50; }
button[data-baseweb="tab"] { font-family: 'Poppins', sans-serif; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# Plotly template in the same identity.
fd_template = pio.templates["plotly_white"].layout.template
fd_template.layout.font = dict(family="Poppins, sans-serif", color=INK, size=13)
fd_template.layout.title = dict(font=dict(family="Fraunces, serif", size=18, color=INK))
fd_template.layout.colorway = CATEGORICAL
fd_template.layout.paper_bgcolor = "rgba(0,0,0,0)"
fd_template.layout.plot_bgcolor = "rgba(0,0,0,0)"
fd_template.layout.xaxis = dict(gridcolor="#EAF3FB", zerolinecolor="#EAF3FB")
fd_template.layout.yaxis = dict(gridcolor="#EAF3FB", zerolinecolor="#EAF3FB")
fd_template.layout.legend = dict(orientation="h", yanchor="bottom", y=1.02, x=0)
fd_template.layout.margin = dict(t=130)
fd_template.layout.title.y = 0.98
pio.templates["firstday"] = fd_template
px.defaults.template = "firstday"


@st.cache_data
def q(sql: str):
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.execute(sql).df()


if not DB_PATH.exists():
    st.error("Database not found. Run `make run` first.")
    st.stop()

# Fixed account -> color mapping, shared by every chart.
account_names = q("select account_name from dim_accounts order by account_id")
ACCOUNT_COLORS = {
    name: CATEGORICAL[i % len(CATEGORICAL)]
    for i, name in enumerate(account_names["account_name"])
}

head_logo, head_title = st.columns([1, 11])
head_logo.image(LOGO, width=72)
head_title.title("AI usage — 3-day sample")

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
    fig = px.funnel(funnel, x="sessions", y="stage")
    fig.update_traces(marker_color=BLUE, textfont=dict(family="Poppins", color="white"))
    st.plotly_chart(fig, use_container_width=True)

with tab_cost:
    left, right = st.columns(2)
    daily_cost = q("""
        select event_date, account_name, ai_cost_usd_estimated
        from daily_account_metrics order by event_date
    """)
    labels = {"event_date": "", "account_name": "account",
              "ai_cost_usd_estimated": "USD (estimated)", "events": "events"}
    cost_fig = px.bar(daily_cost, x="event_date", y="ai_cost_usd_estimated",
                      color="account_name", color_discrete_map=ACCOUNT_COLORS,
                      labels=labels, title="Daily estimated AI cost by account")
    cost_fig.update_xaxes(dtick=86400000, tickformat="%b %d")
    left.plotly_chart(cost_fig, use_container_width=True)
    growth = q("""
        select event_date, account_name, events
        from daily_account_metrics order by event_date
    """)
    growth_fig = px.line(growth, x="event_date", y="events", color="account_name",
                         color_discrete_map=ACCOUNT_COLORS, markers=True,
                         labels=labels, title="Daily events by account")
    growth_fig.update_xaxes(dtick=86400000, tickformat="%b %d")
    right.plotly_chart(growth_fig, use_container_width=True)
    with st.expander("Data table"):
        st.dataframe(q("select * from rpt_daily_cost_by_account"),
                     use_container_width=True)

with tab_models:
    left, right = st.columns(2)
    latency = q("""
        select model, median_latency_ms as median_ms, p95_latency_ms as p95_ms
        from rpt_latency_by_model order by median_ms
    """)
    left.plotly_chart(
        px.bar(latency.melt(id_vars="model", var_name="metric", value_name="ms"),
               x="model", y="ms", color="metric", barmode="group",
               color_discrete_map={"median_ms": BLUE, "p95_ms": "#D98E00"},
               title="Latency by model (median vs p95)"),
        use_container_width=True,
    )
    acceptance = q(
        "select model, acceptance_rate_pct from rpt_acceptance_by_model"
    )
    accept_fig = px.bar(acceptance, x="model", y="acceptance_rate_pct",
                        title="Acceptance rate by model (%)")
    accept_fig.update_traces(marker_color=BLUE)
    right.plotly_chart(accept_fig, use_container_width=True)
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
    reasons_fig = px.bar(reasons, x="rows", y="reason", orientation="h",
                         title="Rejected rows by reason")
    reasons_fig.update_traces(marker_color=BLUE)
    left.plotly_chart(reasons_fig, use_container_width=True)
    right.subheader("Rejected rows")
    right.dataframe(
        q("""
            select rejection_stage, rejection_reason, event_id,
                   source_file, line_number
            from rejected_events order by source_file, line_number
        """),
        use_container_width=True,
    )
