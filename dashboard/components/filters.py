"""Global filters shared by every dashboard page.

Filters (date range + channels) are persisted in st.session_state so they
survive page navigation within the multipage app.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from dashboard.db_connector import WarehouseClient


def _date_bounds(client: WarehouseClient) -> tuple[dt.date, dt.date]:
    """Returns (min_date, max_date) from mart_revenue_daily, falling back
    to a 90-day window ending today when no data is loaded yet."""
    if client.table_exists("mart_revenue_daily"):
        cast = client.date_cast("period")
        df = client.query(
            f"SELECT MIN({cast}) AS mn, MAX({cast}) AS mx FROM mart_revenue_daily"
        )
        if not df.empty and pd.notna(df.loc[0, "mn"]) and pd.notna(df.loc[0, "mx"]):
            return (
                pd.to_datetime(df.loc[0, "mn"]).date(),
                pd.to_datetime(df.loc[0, "mx"]).date(),
            )

    today = dt.date.today()
    return today - dt.timedelta(days=90), today


def _channel_choices(client: WarehouseClient) -> list[str]:
    """Distinct channels from stg_orders (or mart_channel_performance)."""
    for table, column in (("stg_orders", "channel"), ("mart_channel_performance", "channel")):
        if client.table_exists(table):
            df = client.query(f"SELECT DISTINCT {column} AS channel FROM {table} ORDER BY 1")
            if not df.empty:
                return df["channel"].astype(str).tolist()
    return []


def render_global_filters(client: WarehouseClient) -> dict:
    """Draws the shared sidebar filter controls and returns the selection.

    Keys:
      start, end  — datetime.date bounds
      channels    — list of selected channel names
    """
    min_date, max_date = _date_bounds(client)
    channels = _channel_choices(client)

    with st.sidebar:
        st.markdown("### Global filters")

        start = st.date_input(
            "Start date",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="global_start_date",
        )
        end = st.date_input(
            "End date",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="global_end_date",
        )

        selected = st.multiselect(
            "Channels",
            options=channels,
            default=channels,
            key="global_channels",
        )

    if isinstance(start, tuple):  # some Streamlit versions return a tuple
        start = start[0]
    if isinstance(end, tuple):
        end = end[0]

    return {"start": start, "end": end, "channels": list(selected) or channels}


def order_where_clause(client: WarehouseClient, filters: dict) -> str:
    """Builds a SQL WHERE clause (without the leading WHERE) for stg_orders
    date + channel filters, or an empty string when there's nothing to
    filter on."""
    clauses: list[str] = []
    start, end = filters["start"], filters["end"]
    if start and end:
        cast = client.date_cast("order_date")
        clauses.append(f"{cast} BETWEEN DATE '{start}' AND DATE '{end}'")
    channels = filters["channels"]
    if channels:
        clauses.append(client.channel_filter(channels, column="channel"))
    return " AND ".join(clauses)
