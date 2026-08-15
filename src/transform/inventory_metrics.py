"""Inventory health metrics: sell-through, reorder points, dead stock.

Two canonical inputs:

  orders              one row per order line: product_key, quantity, order_date
  inventory_snapshot  one row per product per snapshot: product_key,
                       on_hand_qty, snapshot_date, lead_time_days (supplier
                       replenishment lead time, used for reorder point)
"""

from __future__ import annotations

import pandas as pd

DEFAULT_DEAD_STOCK_DAYS = 90


def calculate_sell_through(units_sold: float, beginning_inventory: float) -> float:
    """Sell-through rate = units sold / beginning inventory, 0.0-1.0+.
    Returns 0.0 if there was no beginning inventory to sell through."""
    if not beginning_inventory:
        return 0.0
    return round(units_sold / beginning_inventory, 4)


def calculate_reorder_point(avg_daily_sales: float, lead_time_days: float, safety_stock: float = 0.0) -> float:
    """Reorder point = (average daily sales * lead time) + safety stock."""
    return round(avg_daily_sales * lead_time_days + safety_stock, 2)


def calculate_sell_through_by_product(orders: pd.DataFrame, inventory_snapshot: pd.DataFrame) -> pd.DataFrame:
    """Sell-through rate per product, using each product's most recent
    inventory snapshot as beginning inventory."""
    if orders.empty or inventory_snapshot.empty:
        return pd.DataFrame(columns=["product_key", "units_sold", "beginning_inventory", "sell_through_rate"])

    units_sold = orders.groupby("product_key")["quantity"].sum().reset_index(name="units_sold")
    latest_snapshot = (
        inventory_snapshot.sort_values("snapshot_date")
        .groupby("product_key")
        .tail(1)[["product_key", "on_hand_qty"]]
        .rename(columns={"on_hand_qty": "beginning_inventory"})
    )
    merged = units_sold.merge(latest_snapshot, on="product_key", how="outer").fillna(0)
    merged["sell_through_rate"] = merged.apply(
        lambda r: calculate_sell_through(r["units_sold"], r["beginning_inventory"]), axis=1
    )
    return merged


def calculate_reorder_points(orders: pd.DataFrame, inventory_snapshot: pd.DataFrame, window_days: int = 30) -> pd.DataFrame:
    """Reorder point per product based on trailing average daily sales
    over the given window and each product's lead_time_days."""
    if orders.empty or inventory_snapshot.empty:
        return pd.DataFrame(columns=["product_key", "avg_daily_sales", "lead_time_days", "reorder_point"])

    avg_daily_sales = (
        orders.groupby("product_key")["quantity"].sum().reset_index(name="total_units")
    )
    avg_daily_sales["avg_daily_sales"] = (avg_daily_sales["total_units"] / window_days).round(4)

    lead_times = (
        inventory_snapshot.sort_values("snapshot_date")
        .groupby("product_key")
        .tail(1)[["product_key", "lead_time_days"]]
    )
    merged = avg_daily_sales.merge(lead_times, on="product_key", how="inner")
    merged["reorder_point"] = merged.apply(
        lambda r: calculate_reorder_point(r["avg_daily_sales"], r["lead_time_days"]), axis=1
    )
    return merged[["product_key", "avg_daily_sales", "lead_time_days", "reorder_point"]]


def identify_dead_stock(
    orders: pd.DataFrame, inventory_snapshot: pd.DataFrame,
    as_of: pd.Timestamp | None = None, days_threshold: int = DEFAULT_DEAD_STOCK_DAYS,
) -> pd.DataFrame:
    """Products with on-hand inventory but no sales in the last
    days_threshold days (or no sales ever)."""
    if inventory_snapshot.empty:
        return pd.DataFrame(columns=["product_key", "on_hand_qty", "days_since_last_sale"])

    latest_snapshot = (
        inventory_snapshot.sort_values("snapshot_date")
        .groupby("product_key")
        .tail(1)[["product_key", "on_hand_qty"]]
    )

    if orders.empty:
        result = latest_snapshot.copy()
        result["days_since_last_sale"] = float("inf")
    else:
        order_dates = pd.to_datetime(orders["order_date"], errors="coerce")
        as_of = pd.Timestamp(as_of) if as_of is not None else order_dates.max()
        last_sale = (
            orders.assign(_order_date=order_dates)
            .groupby("product_key")["_order_date"]
            .max()
            .reset_index(name="last_sale_date")
        )
        result = latest_snapshot.merge(last_sale, on="product_key", how="left")
        result["days_since_last_sale"] = (as_of - result["last_sale_date"]).dt.days
        result["days_since_last_sale"] = result["days_since_last_sale"].fillna(float("inf"))
        result = result.drop(columns=["last_sale_date"])

    stocked = result[result["on_hand_qty"] > 0]
    dead = stocked[stocked["days_since_last_sale"] > days_threshold]
    return dead.reset_index(drop=True)
