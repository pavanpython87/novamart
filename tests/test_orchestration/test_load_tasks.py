import datetime as dt
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.load.dual_loader import DualLoader
from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.tasks.load_tasks import (
    load_table,
    write_bigquery_tables,
    write_duckdb_tables,
)

FACT_ORDERS_COLUMNS = [
    "order_id", "customer_key", "product_key", "channel_key", "date_key",
    "quantity", "gross_revenue", "platform_fee", "payment_processing_fee",
    "returns_and_refunds", "discounts_and_promotions", "net_revenue", "cogs", "gross_profit",
]


def _fact_orders_df():
    return pd.DataFrame([
        ["O1", "C1", "P1", "shopify", dt.date(2024, 1, 1), 1, 100.0, 3.2, 3.2, 0.0, 0.0, 93.6, 40.0, 53.6],
    ], columns=FACT_ORDERS_COLUMNS)


@pytest.fixture
def duckdb_loader():
    loader = DuckDBLoader(":memory:")
    loader.create_schema()
    yield loader
    loader.close()


def test_load_table_loads_nonempty_df(duckdb_loader):
    dual = DualLoader(duckdb_loader, backend="duckdb")
    result = load_table.fn("fact_orders", _fact_orders_df(), dual)
    assert result == {"duckdb": "loaded"}


def test_load_table_empty_df_returns_empty_dict(duckdb_loader):
    dual = DualLoader(duckdb_loader, backend="duckdb")
    result = load_table.fn("fact_orders", pd.DataFrame(), dual)
    assert result == {}


def test_write_duckdb_tables_creates_and_replaces_tables(duckdb_loader):
    tables = {"mart_revenue_daily": pd.DataFrame({"date": ["2024-01-01"], "revenue": [100.0]})}
    written = write_duckdb_tables.fn(duckdb_loader, tables)
    assert written == ["mart_revenue_daily"]
    result = duckdb_loader.conn.execute("SELECT * FROM mart_revenue_daily").fetchdf()
    assert len(result) == 1


def test_write_duckdb_tables_skips_empty_frames(duckdb_loader):
    written = write_duckdb_tables.fn(duckdb_loader, {"empty_mart": pd.DataFrame()})
    assert written == []


def test_write_bigquery_tables_loads_nonempty_frames():
    bigquery_loader = MagicMock()
    tables = {
        "stg_orders": pd.DataFrame({"order_id": ["O1"]}),
        "mart_revenue_daily": pd.DataFrame({"date": ["2024-01-01"], "revenue": [100.0]}),
    }
    written = write_bigquery_tables.fn(bigquery_loader, tables)
    assert written == ["stg_orders", "mart_revenue_daily"]
    assert bigquery_loader.load_dataframe.call_count == 2
    bigquery_loader.load_dataframe.assert_any_call(
        "stg_orders", tables["stg_orders"], write_disposition="WRITE_TRUNCATE",
    )


def test_write_bigquery_tables_skips_empty_frames():
    bigquery_loader = MagicMock()
    written = write_bigquery_tables.fn(bigquery_loader, {"empty_mart": pd.DataFrame()})
    assert written == []
    bigquery_loader.load_dataframe.assert_not_called()
