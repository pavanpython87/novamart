import pandas as pd

from src.orchestration.tasks.transform_tasks import (
    build_analytics,
    calculate_order_economics,
    map_to_canonical_orders,
)


def test_map_to_canonical_orders_renames_columns():
    df = pd.DataFrame({"order_id": ["1"], "total_amount": [100.0]})
    field_map = {"order_id": "order_id", "gross_revenue": "total_amount"}
    result = map_to_canonical_orders(df, "shopify", field_map)
    assert result["gross_revenue"].iloc[0] == 100.0
    assert result["channel"].iloc[0] == "shopify"


def test_map_to_canonical_orders_uses_defaults_for_missing_source_column():
    df = pd.DataFrame({"order_id": ["1"]})
    field_map = {"order_id": "order_id", "discount_amount": "discount_col"}
    result = map_to_canonical_orders(df, "pos", field_map, defaults={"discount_amount": 0.0})
    assert result["discount_amount"].iloc[0] == 0.0


def test_map_to_canonical_orders_empty_df():
    df = pd.DataFrame()
    result = map_to_canonical_orders(df, "shopify", {"order_id": "order_id"})
    assert result.empty


def test_calculate_order_economics_task():
    df = pd.DataFrame([
        {"channel": "pos", "gross_revenue": 100.0, "payment_method": "cash",
         "discount_amount": 0.0, "refund_amount": 0.0, "restocking_fee": 0.0,
         "unit_cost": 40.0, "quantity": 1},
    ])
    result = calculate_order_economics.fn(df)
    assert result["net_revenue"].iloc[0] == 100.0


def test_build_analytics_task():
    orders = pd.DataFrame([
        {"customer_key": "A", "order_date": "2024-01-01", "net_revenue": 100.0},
    ])
    result = build_analytics.fn(orders)
    assert result.loc[result["customer_key"] == "A", "aov"].iloc[0] == 100.0
