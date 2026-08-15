"""Shipping/carrier performance analytics.

Canonical shipment shape: one row per shipment with tracking_number,
carrier, ship_date, delivery_date (nullable if not yet delivered),
promised_delivery_date (nullable), shipping_cost.
"""

from __future__ import annotations

import pandas as pd


def calculate_delivery_days(shipments: pd.DataFrame) -> pd.DataFrame:
    """Adds a delivery_days column (NaN for shipments not yet delivered)."""
    if shipments.empty:
        return shipments.assign(delivery_days=pd.Series(dtype="float64"))

    ship_dates = pd.to_datetime(shipments["ship_date"], errors="coerce")
    delivery_dates = pd.to_datetime(shipments["delivery_date"], errors="coerce")
    result = shipments.copy()
    result["delivery_days"] = (delivery_dates - ship_dates).dt.days
    return result


def calculate_on_time_rate(shipments: pd.DataFrame) -> pd.DataFrame:
    """Adds an on_time boolean column: delivered on/before promised_delivery_date.
    Shipments without a promised date or not yet delivered are excluded (NaN)."""
    if shipments.empty:
        return shipments.assign(on_time=pd.Series(dtype="object"))

    delivery_dates = pd.to_datetime(shipments["delivery_date"], errors="coerce")
    promised_dates = pd.to_datetime(shipments.get("promised_delivery_date"), errors="coerce")
    result = shipments.copy()
    on_time = delivery_dates <= promised_dates
    on_time = on_time.where(delivery_dates.notna() & promised_dates.notna())
    result["on_time"] = on_time
    return result


def carrier_performance(shipments: pd.DataFrame) -> pd.DataFrame:
    """Per-carrier avg delivery days, on-time rate, avg shipping cost."""
    if shipments.empty:
        return pd.DataFrame(columns=["carrier", "avg_delivery_days", "on_time_rate", "avg_shipping_cost", "shipment_count"])

    enriched = calculate_on_time_rate(calculate_delivery_days(shipments))
    grouped = enriched.groupby("carrier").agg(
        avg_delivery_days=("delivery_days", "mean"),
        on_time_rate=("on_time", "mean"),
        avg_shipping_cost=("shipping_cost", "mean"),
        shipment_count=("carrier", "size"),
    ).reset_index()
    grouped["avg_delivery_days"] = grouped["avg_delivery_days"].round(2)
    grouped["on_time_rate"] = grouped["on_time_rate"].round(4)
    grouped["avg_shipping_cost"] = grouped["avg_shipping_cost"].round(2)
    return grouped


def calculate_shipping_cost_pct_of_revenue(shipments: pd.DataFrame, orders: pd.DataFrame) -> float:
    """Total shipping cost as a percentage of total gross order revenue."""
    total_shipping = shipments["shipping_cost"].sum() if not shipments.empty else 0.0
    total_revenue = orders["gross_revenue"].sum() if not orders.empty else 0.0
    if not total_revenue:
        return 0.0
    return round(total_shipping / total_revenue, 4)
