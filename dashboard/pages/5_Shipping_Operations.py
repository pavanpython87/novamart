"""Dashboard 5 — Shipping & fulfillment.

Carrier comparison and delivery-time analysis come from fact_shipments
when loaded. Return-rate analysis always works off stg_orders
(returns_and_refunds > 0), so the page stays useful even before the
shipping facts are populated.
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

st.set_page_config(page_title="Shipping & Fulfillment", layout="wide", page_icon="🚚")

client = get_client()
filters = render_global_filters(client)

st.title("Shipping & Fulfillment")
st.caption("Carrier performance, delivery times, and return analysis.")

has_shipments = client.table_exists("fact_shipments")
shipments = pd.DataFrame()
if has_shipments:
    shipments = client.query("SELECT * FROM fact_shipments")
    has_shipments = has_data(shipments)

if not has_shipments:
    st.info(
        "🚚 No shipment facts (fact_shipments) loaded yet. "
        "Showing return analysis derived from orders instead."
    )

if not client.table_exists("stg_orders"):
    empty_state("No order data loaded. Run the pipeline first.", icon="🚧")
    st.stop()

where = order_where_clause(client, filters)
where_sql = f"WHERE {where}" if where else ""

# -- carrier comparison (when loaded) -----------------------------------
if has_shipments:
    shipments["delivery_days"] = (
        pd.to_datetime(shipments["delivery_date_key"], errors="coerce")
        - pd.to_datetime(shipments["ship_date_key"], errors="coerce")
    ).dt.days

    total_shipments = len(shipments)
    delivered = int(shipments["delivery_date_key"].notna().sum())
    avg_days = shipments["delivery_days"].mean()
    total_cost = float(shipments["shipping_cost"].sum()) if "shipping_cost" in shipments else 0.0

    metric_row([
        ("Shipments", format_number(total_shipments), None),
        ("Delivered", format_number(delivered), None),
        ("Avg delivery days", f"{avg_days:.1f}" if pd.notna(avg_days) else "—", None),
        ("Total shipping cost", format_currency(total_cost), None),
    ])

    st.subheader("Shipments by carrier")
    carrier = shipments["carrier"].value_counts().reset_index()
    carrier.columns = ["carrier", "shipments"]
    fig = px.pie(carrier, values="shipments", names="carrier", hole=0.45)
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Avg delivery days by carrier")
        delivery = shipments.groupby("carrier")["delivery_days"].mean().round(1).reset_index()
        fig = px.bar(delivery, x="carrier", y="delivery_days",
                     labels={"delivery_days": "Avg delivery days", "carrier": ""})
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.subheader("Shipping cost by carrier")
        cost = shipments.groupby("carrier")["shipping_cost"].sum().round(2).reset_index()
        fig = px.bar(cost, x="carrier", y="shipping_cost",
                     labels={"shipping_cost": "Shipping cost", "carrier": ""})
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# -- return analysis ----------------------------------------------------
st.subheader("Return analysis")
returns = client.query(
    f"""
    SELECT
        channel,
        COUNT(*) AS order_lines,
        SUM(CASE WHEN returns_and_refunds > 0 THEN 1 ELSE 0 END) AS returned_lines,
        SUM(returns_and_refunds) AS refund_total
    FROM stg_orders
    {where_sql}
    GROUP BY channel
    ORDER BY channel
    """
)
if has_data(returns):
    returns["return_rate"] = returns["returned_lines"] / returns["order_lines"].replace(0, pd.NA)
    total_lines = int(returns["order_lines"].sum())
    total_returned = int(returns["returned_lines"].sum())
    total_refunds = float(returns["refund_total"].sum())

    metric_row([
        ("Order lines", format_number(total_lines), None),
        ("Returned lines", format_number(total_returned), None),
        ("Return rate", f"{total_returned / total_lines:.1%}" if total_lines else "0%", None),
        ("Refunds issued", format_currency(total_refunds), None),
    ])

    fig = px.bar(
        returns, x="channel", y="return_rate",
        labels={"return_rate": "Return rate", "channel": ""},
    )
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(returns.round(4), use_container_width=True, hide_index=True)
else:
    empty_state("No return data for the current filters.", icon="🔍")
