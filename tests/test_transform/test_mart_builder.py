import pandas as pd

from src.transform.mart_builder import (
    build_all_marts,
    build_channel_performance_mart,
    build_customer_ltv_mart,
    build_inventory_health_mart,
    build_product_performance_mart,
    build_revenue_mart,
)

ORDERS = pd.DataFrame([
    {"customer_key": "C1", "product_key": "P1", "channel": "shopify", "order_date": "2024-01-01",
     "quantity": 2, "gross_revenue": 100.0, "platform_fee": 3.2, "payment_processing_fee": 3.2,
     "net_revenue": 93.6, "gross_profit": 53.6},
    {"customer_key": "C2", "product_key": "P2", "channel": "amazon", "order_date": "2024-01-02",
     "quantity": 1, "gross_revenue": 50.0, "platform_fee": 5.0, "payment_processing_fee": 1.75,
     "net_revenue": 43.25, "gross_profit": 20.0},
])

INVENTORY = pd.DataFrame([
    {"product_key": "P1", "on_hand_qty": 20, "snapshot_date": "2024-01-05", "lead_time_days": 7},
    {"product_key": "P2", "on_hand_qty": 5, "snapshot_date": "2024-01-05", "lead_time_days": 10},
])


def test_build_revenue_mart():
    result = build_revenue_mart(ORDERS, granularity="daily")
    assert len(result) == 2
    assert "net_revenue" in result.columns


def test_build_customer_ltv_mart():
    result = build_customer_ltv_mart(ORDERS).set_index("customer_key")
    assert result.loc["C1", "clv"] == 93.6


def test_build_product_performance_mart():
    result = build_product_performance_mart(ORDERS).set_index("product_key")
    assert result.loc["P1", "units_sold"] == 2
    assert result.loc["P1", "gross_profit"] == 53.6


def test_build_inventory_health_mart():
    result = build_inventory_health_mart(ORDERS, INVENTORY, as_of=pd.Timestamp("2024-01-05")).set_index("product_key")
    assert "sell_through_rate" in result.columns
    assert "is_dead_stock" in result.columns


def test_build_channel_performance_mart():
    result = build_channel_performance_mart(ORDERS).set_index("channel")
    assert result.loc["shopify", "order_count"] == 1
    assert result.loc["shopify", "gross_profit"] == 53.6


def test_build_all_marts_returns_five_tables():
    marts = build_all_marts(ORDERS, INVENTORY, as_of=pd.Timestamp("2024-01-05"))
    assert set(marts.keys()) == {
        "mart_revenue_daily", "mart_customer_ltv", "mart_product_performance",
        "mart_inventory_health", "mart_channel_performance",
    }
    for df in marts.values():
        assert isinstance(df, pd.DataFrame)


def test_build_all_marts_empty_orders():
    empty = pd.DataFrame(columns=ORDERS.columns)
    marts = build_all_marts(empty)
    assert all(df.empty for df in marts.values())
