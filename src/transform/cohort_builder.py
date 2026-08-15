"""Customer cohort analysis by acquisition month, with retention curves.

Canonical input: one row per order line with customer_key and order_date.
"""

from __future__ import annotations

import pandas as pd


def assign_cohorts(orders: pd.DataFrame) -> pd.DataFrame:
    """Adds acquisition_month (customer's first order month, as a Period)
    and order_month columns to the orders DataFrame."""
    if orders.empty:
        return orders.assign(
            acquisition_month=pd.Series(dtype="period[M]"),
            order_month=pd.Series(dtype="period[M]"),
        )

    dates = pd.to_datetime(orders["order_date"], errors="coerce")
    result = orders.copy()
    result["order_month"] = dates.dt.to_period("M")
    acquisition = result.groupby("customer_key")["order_month"].transform("min")
    result["acquisition_month"] = acquisition
    return result


def build_cohort_sizes(orders: pd.DataFrame) -> pd.DataFrame:
    """Number of distinct customers acquired in each cohort month."""
    if orders.empty:
        return pd.DataFrame(columns=["acquisition_month", "cohort_size"])
    cohorted = assign_cohorts(orders)
    sizes = (
        cohorted[["customer_key", "acquisition_month"]]
        .drop_duplicates()
        .groupby("acquisition_month")
        .size()
        .reset_index(name="cohort_size")
    )
    return sizes


def build_retention_matrix(orders: pd.DataFrame) -> pd.DataFrame:
    """Retention matrix: for each acquisition cohort and each period_offset
    (months since acquisition, 0-indexed), the count and pct of that
    cohort's customers who placed an order in that month."""
    if orders.empty:
        return pd.DataFrame(columns=["acquisition_month", "period_offset", "active_customers", "retention_rate"])

    cohorted = assign_cohorts(orders)
    cohorted["period_offset"] = (
        (cohorted["order_month"].dt.year - cohorted["acquisition_month"].dt.year) * 12
        + (cohorted["order_month"].dt.month - cohorted["acquisition_month"].dt.month)
    )

    active = (
        cohorted[["acquisition_month", "period_offset", "customer_key"]]
        .drop_duplicates()
        .groupby(["acquisition_month", "period_offset"])
        .size()
        .reset_index(name="active_customers")
    )

    sizes = build_cohort_sizes(orders)
    merged = active.merge(sizes, on="acquisition_month", how="left")
    merged["retention_rate"] = (merged["active_customers"] / merged["cohort_size"]).round(4)
    return merged.drop(columns=["cohort_size"])
