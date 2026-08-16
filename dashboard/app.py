"""NovaMart analytics dashboard — landing page.

The six interactive dashboards live in dashboard/pages/ (Streamlit's
multipage layout picks them up automatically and lists them in the
sidebar). This landing page shows a quick warehouse status summary so
users know at a glance whether the pipeline has produced data to explore.
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.ui import empty_state, format_currency
from dashboard.db_connector import get_client

st.set_page_config(page_title="NovaMart Analytics", layout="wide", page_icon="📊")

st.title("NovaMart Analytics")
st.caption(
    "Multi-channel retail intelligence — powered by the NovaMart data pipeline "
    "(SQLite → DuckDB → BigQuery)."
)

client = get_client()

st.subheader("Warehouse status")
tables = client.list_tables()

if not tables:
    empty_state(
        "No serving tables found yet. Run the pipeline first, e.g. "
        "`python scripts/run_pipeline.py --mode full-refresh`, then refresh this page.",
        icon="🚧",
    )
else:
    backend = client.backend.upper()
    st.write(f"Backend: **{backend}** — {len(tables)} tables available.")

    key_tables = [
        "stg_orders",
        "mart_revenue_daily",
        "mart_customer_ltv",
        "mart_product_performance",
        "mart_channel_performance",
    ]
    found = [t for t in key_tables if t in tables]
    st.write("Core marts loaded: " + (", ".join(f"`{t}`" for t in found) or "none"))

    if "mart_revenue_daily" in tables:
        total = client.query("SELECT SUM(net_revenue) AS total FROM mart_revenue_daily")
        if not total.empty and total.loc[0, "total"] is not None:
            st.metric("Total net revenue", format_currency(total.loc[0, "total"]))

st.divider()
st.markdown(
    "Use the **sidebar** to navigate between the six dashboards and apply "
    "global date/channel filters: Executive Summary, Channel Deep-Dive, "
    "Customer Intelligence, Inventory Operations, Shipping & Fulfillment, "
    "and Pipeline Health."
)
