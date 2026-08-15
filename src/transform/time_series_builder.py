"""Daily/weekly/monthly/quarterly revenue and order-count rollups.

Canonical input: one row per order line with order_date and net_revenue.
"""

from __future__ import annotations

import pandas as pd

_FREQ_MAP = {
    "daily": "D",
    "weekly": "W",
    "monthly": "ME",
    "quarterly": "QE",
}

_EMPTY_COLUMNS = ["period", "net_revenue", "order_count"]


def build_time_series(orders: pd.DataFrame, granularity: str) -> pd.DataFrame:
    """Aggregates orders into net_revenue and order_count buckets at the
    given granularity: 'daily' | 'weekly' | 'monthly' | 'quarterly'."""
    if granularity not in _FREQ_MAP:
        raise ValueError(f"Unsupported granularity: {granularity}")
    if orders.empty:
        return pd.DataFrame(columns=_EMPTY_COLUMNS)

    dates = pd.to_datetime(orders["order_date"], errors="coerce")
    working = orders.assign(_order_date=dates).dropna(subset=["_order_date"])
    grouped = (
        working.set_index("_order_date")
        .resample(_FREQ_MAP[granularity])
        .agg(net_revenue=("net_revenue", "sum"), order_count=("net_revenue", "size"))
        .reset_index()
        .rename(columns={"_order_date": "period"})
    )
    grouped["net_revenue"] = grouped["net_revenue"].round(2)
    return grouped


def build_all_rollups(orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Returns a dict of granularity -> time series DataFrame for all four
    standard granularities."""
    return {granularity: build_time_series(orders, granularity) for granularity in _FREQ_MAP}
