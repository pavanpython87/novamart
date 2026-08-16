"""Shared dashboard UI helpers: number formatting and empty-state
rendering, so the six pages stay visually consistent.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def format_currency(value: float) -> str:
    if value is None or pd.isna(value):
        return "$0"
    return f"${value:,.0f}"


def format_number(value: float) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{value:,.0f}"


def format_pct(value: float) -> str:
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{value:.1%}"


def empty_state(message: str, icon: str = "ℹ️") -> None:
    st.info(f"{icon} {message}")


def has_data(df: pd.DataFrame | None) -> bool:
    return df is not None and not df.empty


def metric_row(items: list[tuple[str, float | str, str | None]]) -> None:
    """Renders a row of st.metric cards. Each item is (label, value, delta)."""
    cols = st.columns(len(items))
    for col, (label, value, delta) in zip(cols, items, strict=True):
        col.metric(label, value, delta)
