"""Customer-level analytics: CLV, AOV, purchase frequency, churn risk, RFM.

Operates on a canonical per-order DataFrame with columns:

    customer_key       resolved cross-channel customer identifier
    order_date         ISO date/datetime string or Timestamp
    net_revenue         float, from revenue_calculator

All functions accept the full order-level DataFrame and return one row
per customer_key.
"""

from __future__ import annotations

import pandas as pd

CHURN_RISK_INACTIVITY_DAYS = {
    "low": 60,
    "medium": 120,
    "high": 180,
}


def _as_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def calculate_aov(orders: pd.DataFrame) -> pd.DataFrame:
    """Average order value per customer."""
    if orders.empty:
        return pd.DataFrame(columns=["customer_key", "aov"])
    grouped = orders.groupby("customer_key")["net_revenue"].mean().round(2)
    return grouped.reset_index(name="aov")


def calculate_clv(orders: pd.DataFrame) -> pd.DataFrame:
    """Simple historical CLV: total net revenue generated to date per
    customer. (Historical, not predictive, CLV.)"""
    if orders.empty:
        return pd.DataFrame(columns=["customer_key", "clv"])
    grouped = orders.groupby("customer_key")["net_revenue"].sum().round(2)
    return grouped.reset_index(name="clv")


def calculate_purchase_frequency(orders: pd.DataFrame) -> pd.DataFrame:
    """Number of distinct orders per customer."""
    if orders.empty:
        return pd.DataFrame(columns=["customer_key", "purchase_frequency"])
    grouped = orders.groupby("customer_key").size()
    return grouped.reset_index(name="purchase_frequency")


def score_churn_risk(orders: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Churn risk per customer based on days since their most recent order.

    low: <= 60 days, medium: 61-120 days, high: 121-180 days, lost: > 180 days.
    """
    if orders.empty:
        return pd.DataFrame(columns=["customer_key", "days_since_last_order", "churn_risk"])

    dates = _as_datetime(orders["order_date"])
    as_of = pd.Timestamp(as_of) if as_of is not None else dates.max()

    last_order = (
        orders.assign(_order_date=dates)
        .groupby("customer_key")["_order_date"]
        .max()
        .reset_index(name="last_order_date")
    )
    last_order["days_since_last_order"] = (as_of - last_order["last_order_date"]).dt.days

    def _risk(days: int) -> str:
        if days <= CHURN_RISK_INACTIVITY_DAYS["low"]:
            return "low"
        if days <= CHURN_RISK_INACTIVITY_DAYS["medium"]:
            return "medium"
        if days <= CHURN_RISK_INACTIVITY_DAYS["high"]:
            return "high"
        return "lost"

    last_order["churn_risk"] = last_order["days_since_last_order"].apply(_risk)
    return last_order[["customer_key", "days_since_last_order", "churn_risk"]]


def calculate_rfm(orders: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Recency (days since last order), Frequency (order count), Monetary
    (total net revenue) per customer, each scored 1 (worst) to 5 (best)
    via quintiles, plus a combined rfm_segment string like "555"."""
    if orders.empty:
        return pd.DataFrame(columns=[
            "customer_key", "recency", "frequency", "monetary",
            "r_score", "f_score", "m_score", "rfm_segment",
        ])

    dates = _as_datetime(orders["order_date"])
    valid = dates.notna()
    if not valid.all():
        # Orders whose dates can't be parsed can't contribute a meaningful
        # recency; dropping them avoids NaN recency values that would
        # break quintile scoring below.
        orders = orders.loc[valid]
        dates = dates.loc[valid]
    if orders.empty:
        return pd.DataFrame(columns=[
            "customer_key", "recency", "frequency", "monetary",
            "r_score", "f_score", "m_score", "rfm_segment",
        ])

    as_of = pd.Timestamp(as_of) if as_of is not None else dates.max()

    grouped = (
        orders.assign(_order_date=dates)
        .groupby("customer_key")
        .agg(
            recency=("_order_date", lambda s: (as_of - s.max()).days),
            frequency=("_order_date", "count"),
            monetary=("net_revenue", "sum"),
        )
        .reset_index()
    )
    grouped["monetary"] = grouped["monetary"].round(2)

    def _quintile_score(series: pd.Series, ascending: bool) -> pd.Series:
        if series.nunique() < 2:
            return pd.Series([3] * len(series), index=series.index)
        ranks = series.rank(method="first", ascending=ascending, pct=True)
        return (ranks * 5).apply(lambda x: min(5, int(x) + 1))

    grouped["r_score"] = _quintile_score(grouped["recency"], ascending=False)
    grouped["f_score"] = _quintile_score(grouped["frequency"], ascending=True)
    grouped["m_score"] = _quintile_score(grouped["monetary"], ascending=True)
    grouped["rfm_segment"] = (
        grouped["r_score"].astype(str) + grouped["f_score"].astype(str) + grouped["m_score"].astype(str)
    )
    return grouped


def build_customer_analytics(orders: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Combines AOV, CLV, purchase frequency, churn risk, and RFM into a
    single per-customer analytics table."""
    if orders.empty:
        return pd.DataFrame(columns=[
            "customer_key", "aov", "clv", "purchase_frequency",
            "days_since_last_order", "churn_risk",
            "recency", "frequency", "monetary",
            "r_score", "f_score", "m_score", "rfm_segment",
        ])

    result = calculate_aov(orders)
    result = result.merge(calculate_clv(orders), on="customer_key")
    result = result.merge(calculate_purchase_frequency(orders), on="customer_key")
    result = result.merge(score_churn_risk(orders, as_of=as_of), on="customer_key")
    result = result.merge(
        calculate_rfm(orders, as_of=as_of).drop(columns=["frequency"]).rename(
            columns={"monetary": "monetary"}
        ),
        on="customer_key",
    )
    return result
