"""Pre-computed aggregation (mart) tables, built on top of the other
transform-layer modules. Five marts, matching PROJECT_PLAN.md Day 14:

    mart_revenue_daily        daily revenue/order-count time series
    mart_customer_ltv         per-customer CLV/AOV/RFM/churn analytics
    mart_product_performance  per-product units sold, revenue, profit
    mart_inventory_health     per-product sell-through, reorder point, dead stock flag
    mart_channel_performance  per-channel revenue, fees, profit
"""

from __future__ import annotations

import pandas as pd

from src.transform.customer_analytics import build_customer_analytics
from src.transform.inventory_metrics import (
    calculate_reorder_points,
    calculate_sell_through_by_product,
    identify_dead_stock,
)
from src.transform.time_series_builder import build_time_series


def build_revenue_mart(orders: pd.DataFrame, granularity: str = "daily") -> pd.DataFrame:
    return build_time_series(orders, granularity)


def build_customer_ltv_mart(orders: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    return build_customer_analytics(orders, as_of=as_of)


def build_product_performance_mart(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(columns=[
            "product_key", "units_sold", "gross_revenue", "net_revenue", "gross_profit",
        ])
    grouped = orders.groupby("product_key").agg(
        units_sold=("quantity", "sum"),
        gross_revenue=("gross_revenue", "sum"),
        net_revenue=("net_revenue", "sum"),
        gross_profit=("gross_profit", "sum"),
    ).round(2).reset_index()
    return grouped


def build_inventory_health_mart(
    orders: pd.DataFrame, inventory_snapshot: pd.DataFrame, as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if orders.empty or inventory_snapshot.empty:
        return pd.DataFrame(columns=[
            "product_key", "units_sold", "beginning_inventory", "sell_through_rate",
            "avg_daily_sales", "lead_time_days", "reorder_point", "is_dead_stock",
        ])

    sell_through = calculate_sell_through_by_product(orders, inventory_snapshot)
    reorder = calculate_reorder_points(orders, inventory_snapshot)
    dead_stock_keys = set(identify_dead_stock(orders, inventory_snapshot, as_of=as_of)["product_key"])

    merged = sell_through.merge(reorder, on="product_key", how="left")
    merged["is_dead_stock"] = merged["product_key"].isin(dead_stock_keys)
    return merged


def build_channel_performance_mart(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(columns=[
            "channel", "order_count", "gross_revenue", "platform_fee",
            "payment_processing_fee", "net_revenue", "gross_profit",
        ])
    grouped = orders.groupby("channel").agg(
        order_count=("channel", "size"),
        gross_revenue=("gross_revenue", "sum"),
        platform_fee=("platform_fee", "sum"),
        payment_processing_fee=("payment_processing_fee", "sum"),
        net_revenue=("net_revenue", "sum"),
        gross_profit=("gross_profit", "sum"),
    ).round(2).reset_index()
    return grouped


def build_all_marts(
    orders: pd.DataFrame, inventory_snapshot: pd.DataFrame | None = None,
    as_of: pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    inventory_snapshot = inventory_snapshot if inventory_snapshot is not None else pd.DataFrame()
    return {
        "mart_revenue_daily": build_revenue_mart(orders, granularity="daily"),
        "mart_customer_ltv": build_customer_ltv_mart(orders, as_of=as_of),
        "mart_product_performance": build_product_performance_mart(orders),
        "mart_inventory_health": build_inventory_health_mart(orders, inventory_snapshot, as_of=as_of),
        "mart_channel_performance": build_channel_performance_mart(orders),
    }
