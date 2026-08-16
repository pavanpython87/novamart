"""Dashboard 3 — Customer intelligence.

CLV distribution, RFM segments, churn risk, and acquisition cohorts from
mart_customer_ltv (with a first-order-month cohort derived from stg_orders).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.filters import order_where_clause, render_global_filters
from dashboard.components.ui import (
    empty_state,
    format_currency,
    format_number,
    has_data,
    metric_row,
)
from dashboard.db_connector import get_client

st.set_page_config(page_title="Customer Intelligence", layout="wide", page_icon="👥")

client = get_client()
filters = render_global_filters(client)

st.title("Customer Intelligence")
st.caption("Who buys, how much they're worth, and who's at risk of churning.")

if not client.table_exists("mart_customer_ltv"):
    empty_state("No customer analytics loaded. Run the pipeline first.", icon="🚧")
    st.stop()

customers = client.query("SELECT * FROM mart_customer_ltv")
if not has_data(customers):
    empty_state("No customer data matches the current filters.", icon="🔍")
    st.stop()

# -- headline metrics ---------------------------------------------------
total_customers = len(customers)
avg_clv = float(customers["clv"].mean()) if "clv" in customers else 0.0
avg_aov = float(customers["aov"].mean()) if "aov" in customers else 0.0
at_risk = int((customers["churn_risk"].isin(["high", "lost"])).sum()) if "churn_risk" in customers else 0

metric_row([
    ("Customers", format_number(total_customers), None),
    ("Avg CLV", format_currency(avg_clv), None),
    ("Avg AOV", format_currency(avg_aov), None),
    ("At-risk customers", format_number(at_risk), None),
])

# -- CLV distribution + churn risk --------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("CLV distribution")
    if "clv" in customers:
        fig = px.histogram(
            customers, x="clv", nbins=40,
            labels={"clv": "Customer lifetime value", "count": "Customers"},
        )
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("CLV not available.", icon="🔍")

with right:
    st.subheader("Churn risk")
    if "churn_risk" in customers:
        churn = customers["churn_risk"].value_counts().reset_index()
        churn.columns = ["churn_risk", "count"]
        fig = px.pie(churn, values="count", names="churn_risk", hole=0.45)
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("Churn risk not available.", icon="🔍")

# -- RFM segments -------------------------------------------------------
st.subheader("RFM segments")
if "rfm_segment" in customers:
    rfm = customers["rfm_segment"].value_counts().head(15).reset_index()
    rfm.columns = ["segment", "count"]
    fig = px.bar(rfm, x="segment", y="count", labels={"count": "Customers"})
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_state("RFM segments not available.", icon="🔍")

# -- acquisition cohort -------------------------------------------------
st.subheader("Customer acquisition trend")
where = order_where_clause(client, filters)
where_sql = f"WHERE {where}" if where else ""
cohort = client.query(
    f"""
    WITH first_orders AS (
        SELECT customer_key, MIN({client.date_cast('order_date')}) AS first_order
        FROM stg_orders
        {where_sql}
        GROUP BY customer_key
    )
    SELECT DATE_TRUNC('month', first_order) AS cohort_month, COUNT(*) AS customers
    FROM first_orders
    GROUP BY 1
    ORDER BY 1
    """
)
if has_data(cohort):
    cohort["cohort_month"] = pd.to_datetime(cohort["cohort_month"])
    fig = px.bar(cohort, x="cohort_month", y="customers",
                 labels={"cohort_month": "First-purchase month", "customers": "New customers"})
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_state("No acquisition data for the current filters.", icon="🔍")

# -- top customers ------------------------------------------------------
st.subheader("Top customers by lifetime value")
if "clv" in customers:
    top = customers.nlargest(25, "clv")
    st.dataframe(top, use_container_width=True, hide_index=True)
