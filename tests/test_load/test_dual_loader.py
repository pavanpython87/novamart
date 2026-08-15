from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.load.dual_loader import DualLoader
from src.load.duckdb_loader import DuckDBLoader

FACT_ORDERS_COLUMNS = [
    "order_id", "customer_key", "product_key", "channel_key", "date_key",
    "quantity", "gross_revenue", "platform_fee", "payment_processing_fee",
    "returns_and_refunds", "discounts_and_promotions", "net_revenue", "cogs", "gross_profit",
]


def _fact_orders_df():
    import datetime as dt
    return pd.DataFrame([
        ["O1", "C1", "P1", "shopify", dt.date(2024, 1, 1), 1, 100.0, 3.2, 3.2, 0.0, 0.0, 93.6, 40.0, 53.6],
    ], columns=FACT_ORDERS_COLUMNS)


@pytest.fixture
def duckdb_loader():
    loader = DuckDBLoader(":memory:")
    loader.create_schema()
    yield loader
    loader.close()


def test_duckdb_only_backend_loads_only_duckdb(duckdb_loader):
    dual = DualLoader(duckdb_loader, backend="duckdb")
    results = dual.load("fact_orders", _fact_orders_df())
    assert results == {"duckdb": "loaded"}
    assert len(duckdb_loader.conn.execute("SELECT * FROM fact_orders").fetchdf()) == 1


def test_bigquery_backend_requires_bigquery_loader(duckdb_loader):
    with pytest.raises(ValueError):
        DualLoader(duckdb_loader, backend="bigquery")


def test_both_backend_loads_both_destinations(duckdb_loader):
    bq_loader = MagicMock()
    dual = DualLoader(duckdb_loader, bigquery_loader=bq_loader, backend="both")
    results = dual.load("fact_orders", _fact_orders_df())
    assert results == {"duckdb": "loaded", "bigquery": "loaded"}
    assert bq_loader.upsert.called


def test_invalid_backend_raises(duckdb_loader):
    with pytest.raises(ValueError):
        DualLoader(duckdb_loader, backend="not_a_backend")
