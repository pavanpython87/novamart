"""Dashboard 2 — Channel deep-dive.

Revenue waterfall (gross → net → profit), fee analysis, and cross-channel
customer behaviour per selling channel.
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

st.set_page_config(page_title="Channel Deep-Dive", layout="wide", page_icon="📈")

client = get_client()
filters = render_global_filters(client)

st.title("Channel Deep-Dive")
st.caption("How each selling channel (Shopify, Amazon, POS) contributes to revenue and profit.")

if not client.table_exists("stg_orders"):
    empty_state("No order data loaded. Run the pipeline first.", icon="🚧")
    st.stop()

where = order_where_clause(client, filters)
where_sql = f"WHERE {where}" if where else ""

# -- per-channel scorecards ---------------------------------------------
channel_df = client.query(
    f"""
    SELECT
        channel,
        COUNT(DISTINCT order_id) AS order_count,
        SUM(gross_revenue) AS gross_revenue,
        SUM(platform_fee) AS platform_fee,
        SUM(payment_processing_fee) AS payment_processing_fee,
        SUM(returns_and_refunds) AS returns_and_refunds,
        SUM(discounts_and_promotions) AS discounts_and_promotions,
        SUM(net_revenue) AS net_revenue,
        SUM(gross_profit) AS gross_profit
    FROM stg_orders
    {where_sql}
    GROUP BY channel
    ORDER BY net_revenue DESC
    """
)

if not has_data(channel_df):
    empty_state("No data matches the current filters.", icon="🔍")
    st.stop()

channel_choice = st.selectbox(
    "Channel", options=channel_df["channel"].tolist(), index=0
)
row = channel_df[channel_df["channel"] == channel_choice].iloc[0]

metric_row([
    ("Net revenue", format_currency(row["net_revenue"]), None),
    ("Orders", format_number(row["order_count"]), None),
    ("AOV", format_currency(row["net_revenue"] / row["order_count"] if row["order_count"] else 0), None),
    ("Gross profit", format_currency(row["gross_profit"]), None),
])

# -- revenue waterfall ---------------------------------------------------
st.subheader(f"Revenue waterfall — {channel_choice}")
waterfall = pd.DataFrame([
    {"step": "Gross revenue", "amount": float(row["gross_revenue"])},
    {"step": "Platform fees", "amount": -float(row["platform_fee"])},
    {"step": "Payment fees", "amount": -float(row["payment_processing_fee"])},
    {"step": "Returns & refunds", "amount": -float(row["returns_and_refunds"])},
    {"step": "Discounts", "amount": -float(row["discounts_and_promotions"])},
    {"step": "Net revenue", "amount": float(row["net_revenue"])},
])
fig = px.bar(
    waterfall, x="step", y="amount",
    color="amount",
    color_continuous_scale=["#ef4444", "#e5e7eb", "#16a34a"],
    text_auto=".2s",
)
fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0), showlegend=False,
                  coloraxis_showscale=False)
st.plotly_chart(fig, use_container_width=True)

# -- fee analysis + channel comparison -----------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Fee breakdown by channel")
    fees = channel_df[["channel", "platform_fee", "payment_processing_fee"]].melt(
        id_vars="channel", var_name="fee_type", value_name="amount"
    )
    fig = px.bar(
        fees, x="channel", y="amount", color="fee_type", barmode="group",
        labels={"amount": "Fees", "channel": "", "fee_type": ""},
    )
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Net revenue by channel")
    fig = px.bar(
        channel_df, x="channel", y="net_revenue", color="channel",
        labels={"net_revenue": "Net revenue", "channel": ""},
    )
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# -- cross-channel customers --------------------------------------------
st.subheader("Cross-channel customers")
cross = client.query(
    f"""
    SELECT customer_key, COUNT(DISTINCT channel) AS channel_count
    FROM stg_orders
    {where_sql}
    GROUP BY customer_key
    """
)
if has_data(cross):
    total_customers = len(cross)
    cross_channel = int((cross["channel_count"] > 1).sum())
    st.metric("Customers buying on 2+ channels", f"{cross_channel:,} / {total_customers:,}")

    fig = px.histogram(
        cross, x="channel_count", nbins=int(cross["channel_count"].max()),
        labels={"channel_count": "Channels per customer", "count": "Customers"},
    )
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    empty_state("No customer data for the current filters.", icon="🔍")
