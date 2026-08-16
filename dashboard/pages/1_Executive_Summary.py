"""Dashboard 1 — Executive summary.

Scorecards, revenue trends, channel mix, and top/bottom products, all
filtered by the global date + channel selection.
"""

from __future__ import annotations

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

st.set_page_config(page_title="Executive Summary", layout="wide", page_icon="📊")

client = get_client()
filters = render_global_filters(client)

st.title("Executive Summary")
st.caption("One screen for the whole business: revenue, orders, profit, and what's moving.")

if not client.table_exists("stg_orders"):
    empty_state("No order data loaded. Run the pipeline first.", icon="🚧")
    st.stop()

where = order_where_clause(client, filters)
where_sql = f"WHERE {where}" if where else ""

# -- headline metrics ---------------------------------------------------
summary = client.query(
    f"""
    SELECT
        COUNT(DISTINCT order_id) AS orders,
        SUM(net_revenue) AS net_revenue,
        SUM(gross_profit) AS gross_profit,
        SUM(gross_revenue) AS gross_revenue
    FROM stg_orders
    {where_sql}
    """
)
if not has_data(summary):
    empty_state("No data matches the current filters.", icon="🔍")
    st.stop()

orders = int(summary.loc[0, "orders"] or 0)
net_revenue = float(summary.loc[0, "net_revenue"] or 0.0)
gross_profit = float(summary.loc[0, "gross_profit"] or 0.0)
gross_revenue = float(summary.loc[0, "gross_revenue"] or 0.0)
aov = net_revenue / orders if orders else 0.0
margin = gross_profit / gross_revenue if gross_revenue else 0.0

metric_row([
    ("Net revenue", format_currency(net_revenue), None),
    ("Orders", format_number(orders), None),
    ("Average order value", format_currency(aov), None),
    ("Gross profit", format_currency(gross_profit), None),
    ("Profit margin", f"{margin:.1%}", None),
])

# -- revenue trend ------------------------------------------------------
if client.table_exists("mart_revenue_daily"):
    cast = client.date_cast("period")
    trend = client.query(
        f"""
        SELECT {cast} AS period, net_revenue, order_count
        FROM mart_revenue_daily
        WHERE {cast} BETWEEN DATE '{filters['start']}' AND DATE '{filters['end']}'
        ORDER BY 1
        """
    )
    if has_data(trend):
        st.subheader("Revenue trend")
        fig = px.area(
            trend, x="period", y="net_revenue",
            labels={"period": "", "net_revenue": "Net revenue"},
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

# -- channel mix + product leaders --------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Channel mix")
    channel_df = client.query(
        f"""
        SELECT channel, SUM(net_revenue) AS net_revenue
        FROM stg_orders
        {where_sql}
        GROUP BY channel
        ORDER BY net_revenue DESC
        """
    )
    if has_data(channel_df):
        fig = px.pie(
            channel_df, values="net_revenue", names="channel", hole=0.45,
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No channel data for the current filters.", icon="🔍")

with right:
    st.subheader("Top products by net revenue")
    products = client.query(
        f"""
        SELECT product_key, SUM(net_revenue) AS net_revenue, SUM(quantity) AS units_sold
        FROM stg_orders
        {where_sql}
        GROUP BY product_key
        ORDER BY net_revenue DESC
        LIMIT 10
        """
    )
    if has_data(products):
        fig = px.bar(
            products, x="net_revenue", y="product_key", orientation="h",
            labels={"net_revenue": "Net revenue", "product_key": "Product"},
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No product data for the current filters.", icon="🔍")

# -- recent orders ------------------------------------------------------
st.subheader("Recent orders")
recent = client.query(
    f"""
    SELECT order_id, channel, order_date, quantity, net_revenue, status
    FROM stg_orders
    {where_sql}
    ORDER BY order_date DESC
    LIMIT 50
    """
)
if has_data(recent):
    st.dataframe(recent, use_container_width=True, hide_index=True)
else:
    empty_state("No recent orders for the current filters.", icon="🔍")
