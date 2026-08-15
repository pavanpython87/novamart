import pandas as pd

from src.transform.inventory_metrics import (
    calculate_reorder_point,
    calculate_reorder_points,
    calculate_sell_through,
    calculate_sell_through_by_product,
    identify_dead_stock,
)

ORDERS = pd.DataFrame([
    {"product_key": "P1", "quantity": 5, "order_date": "2024-03-01"},
    {"product_key": "P1", "quantity": 3, "order_date": "2024-03-10"},
    {"product_key": "P2", "quantity": 1, "order_date": "2024-01-01"},
])

INVENTORY = pd.DataFrame([
    {"product_key": "P1", "on_hand_qty": 40, "snapshot_date": "2024-03-15", "lead_time_days": 7},
    {"product_key": "P2", "on_hand_qty": 10, "snapshot_date": "2024-03-15", "lead_time_days": 14},
    {"product_key": "P3", "on_hand_qty": 5, "snapshot_date": "2024-03-15", "lead_time_days": 5},
])


def test_calculate_sell_through():
    assert calculate_sell_through(8, 40) == 0.2


def test_calculate_sell_through_zero_beginning_inventory():
    assert calculate_sell_through(8, 0) == 0.0


def test_calculate_reorder_point():
    assert calculate_reorder_point(avg_daily_sales=2.0, lead_time_days=7, safety_stock=5) == 19.0


def test_calculate_sell_through_by_product():
    result = calculate_sell_through_by_product(ORDERS, INVENTORY).set_index("product_key")
    assert result.loc["P1", "units_sold"] == 8
    assert result.loc["P1", "sell_through_rate"] == 0.2
    # P3 has no sales at all -> units_sold 0
    assert result.loc["P3", "units_sold"] == 0


def test_calculate_reorder_points():
    result = calculate_reorder_points(ORDERS, INVENTORY, window_days=30).set_index("product_key")
    assert result.loc["P1", "avg_daily_sales"] == round(8 / 30, 4)
    assert result.loc["P1", "lead_time_days"] == 7


def test_identify_dead_stock_flags_no_recent_sales():
    as_of = pd.Timestamp("2024-03-15")
    dead = identify_dead_stock(ORDERS, INVENTORY, as_of=as_of, days_threshold=30)
    dead_products = set(dead["product_key"])
    # P2's last sale was 2024-01-01 -> 74 days ago -> dead
    assert "P2" in dead_products
    # P3 has stock but no sales ever -> dead
    assert "P3" in dead_products
    # P1 sold recently -> not dead
    assert "P1" not in dead_products


def test_identify_dead_stock_empty_orders_treats_all_stocked_as_dead():
    result = identify_dead_stock(pd.DataFrame(columns=["product_key", "quantity", "order_date"]), INVENTORY)
    assert set(result["product_key"]) == {"P1", "P2", "P3"}
