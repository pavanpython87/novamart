"""Dashboard 4 — Inventory operations.

Stock levels, reorder alerts, and dead-stock flags come from
fact_inventory_daily when the inventory snapshot has been loaded. Until
then, the page falls back to sales-velocity analytics derived from
stg_orders so it's never blank.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.filters import order_where_clause, render_global_filters
from dashboard.components.ui import (
    empty_state,
    format_number,
    has_data,
    metric_row,
)
from dashboard.db_connector import get_client

st.set_page_config(page_title="Inventory Operations", layout="wide", page_icon="📦")

client = get_client()
filters = render_global_filters(client)

st.title("Inventory Operations")
st.caption("Sell-through, velocity, and replenishment signals.")

has_snapshot = client.table_exists("fact_inventory_daily")
if has_snapshot:
    snapshot = client.query("SELECT * FROM fact_inventory_daily")
    has_snapshot = has_data(snapshot)

if not has_snapshot:
    st.info(
        "📦 No inventory snapshot (fact_inventory_daily) loaded yet. "
        "Showing sales-velocity analytics derived from orders instead."
    )

if not client.table_exists("stg_orders"):
    empty_state("No order data loaded. Run the pipeline first.", icon="🚧")
    st.stop()

where = order_where_clause(client, filters)
where_sql = f"WHERE {where}" if where else ""

# -- velocity by product ------------------------------------------------
velocity = client.query(
    f"""
    SELECT
        product_key,
        SUM(quantity) AS units_sold,
        SUM(net_revenue) AS net_revenue,
        COUNT(DISTINCT {client.date_cast('order_date')}) AS selling_days
    FROM stg_orders
    {where_sql}
    GROUP BY product_key
    """
)
if not has_data(velocity):
    empty_state("No inventory/order data matches the current filters.", icon="🔍")
    st.stop()

velocity["units_per_day"] = velocity["units_sold"] / velocity["selling_days"].replace(0, pd.NA)
velocity = velocity.sort_values("units_sold", ascending=False)

total_units = int(velocity["units_sold"].sum())
total_products = len(velocity)

metric_row([
    ("Products with sales", format_number(total_products), None),
    ("Units sold", format_number(total_units), None),
    ("Top product", str(velocity.iloc[0]["product_key"]), None),
    ("Top product units", format_number(velocity.iloc[0]["units_sold"]), None),
])

# -- top movers vs slow movers ------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Fastest movers")
    top = velocity.head(10)
    fig = px.bar(top, x="units_sold", y="product_key", orientation="h",
                 labels={"units_sold": "Units sold", "product_key": ""})
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Slow movers")
    slow = velocity.tail(10).sort_values("units_sold")
    fig = px.bar(slow, x="units_sold", y="product_key", orientation="h",
                 labels={"units_sold": "Units sold", "product_key": ""})
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

# -- sales velocity distribution ----------------------------------------
st.subheader("Sales velocity distribution")
fig = px.histogram(velocity, x="units_per_day", nbins=40,
                   labels={"units_per_day": "Units per day", "count": "Products"})
fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
st.plotly_chart(fig, use_container_width=True)

# -- snapshot detail (when loaded) --------------------------------------
if has_snapshot:
    st.subheader("Stock levels (inventory snapshot)")
    low_stock_threshold = 50
    low_stock = snapshot[snapshot["on_hand_qty"] < low_stock_threshold].sort_values("on_hand_qty")

    metric_row([
        ("Products stocked", format_number(len(snapshot)), None),
        ("Total on-hand units", format_number(int(snapshot["on_hand_qty"].sum())), None),
        ("Low-stock products", format_number(len(low_stock)), None),
        ("Avg lead time (days)", f"{snapshot['lead_time_days'].mean():.1f}", None),
    ])

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("On-hand distribution")
        fig = px.histogram(
            snapshot, x="on_hand_qty", nbins=40,
            labels={"on_hand_qty": "On-hand units", "count": "Products"},
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.subheader(f"Low stock (on-hand < {low_stock_threshold})")
        if has_data(low_stock):
            st.dataframe(
                low_stock[["product_key", "on_hand_qty", "lead_time_days", "snapshot_date_key"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No low-stock products.")
