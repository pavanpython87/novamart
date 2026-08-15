import datetime as dt

import pandas as pd
import pytest

from src.load.duckdb_loader import DuckDBLoader

FACT_ORDERS_COLUMNS = [
    "order_id", "customer_key", "product_key", "channel_key", "date_key",
    "quantity", "gross_revenue", "platform_fee", "payment_processing_fee",
    "returns_and_refunds", "discounts_and_promotions", "net_revenue", "cogs", "gross_profit",
]

CUSTOMER_COLUMNS = [
    "customer_key", "first_name", "last_name", "email", "phone",
    "postal_code", "region", "channels",
]


def _fact_orders_df(rows):
    return pd.DataFrame(rows, columns=FACT_ORDERS_COLUMNS)


@pytest.fixture
def loader():
    loader = DuckDBLoader(":memory:")
    loader.create_schema()
    yield loader
    loader.close()


def test_create_schema_creates_all_tables(loader):
    tables = loader.conn.execute("SHOW TABLES").fetchdf()["name"].tolist()
    assert "fact_orders" in tables
    assert "dim_customers" in tables


def test_upsert_inserts_rows(loader):
    df = _fact_orders_df([
        ["O1", "C1", "P1", "shopify", dt.date(2024, 1, 1), 1, 100.0, 3.2, 3.2, 0.0, 0.0, 93.6, 40.0, 53.6],
    ])
    loader.upsert("fact_orders", df)
    result = loader.conn.execute("SELECT * FROM fact_orders").fetchdf()
    assert len(result) == 1
    assert result.iloc[0]["order_id"] == "O1"


def test_upsert_is_idempotent_and_updates_existing_rows(loader):
    df = _fact_orders_df([
        ["O1", "C1", "P1", "shopify", dt.date(2024, 1, 1), 1, 100.0, 3.2, 3.2, 0.0, 0.0, 93.6, 40.0, 53.6],
    ])
    loader.upsert("fact_orders", df)

    updated = _fact_orders_df([
        ["O1", "C1", "P1", "shopify", dt.date(2024, 1, 1), 1, 100.0, 3.2, 3.2, 0.0, 0.0, 200.0, 40.0, 160.0],
    ])
    loader.upsert("fact_orders", updated)

    result = loader.conn.execute("SELECT * FROM fact_orders").fetchdf()
    assert len(result) == 1
    assert result.iloc[0]["net_revenue"] == 200.0


def test_scd2_new_customer_inserted_as_current(loader):
    incoming = pd.DataFrame([
        ["C1", "Bob", "Smith", "bob@x.com", "+1415", "94105", "CA", "shopify"],
    ], columns=CUSTOMER_COLUMNS)
    loader.upsert_scd2_customers(incoming, as_of=dt.date(2024, 1, 1))

    result = loader.conn.execute("SELECT * FROM dim_customers").fetchdf()
    assert len(result) == 1
    assert result.iloc[0]["is_current"]
    assert result.iloc[0]["effective_date"] == pd.Timestamp(2024, 1, 1)


def test_scd2_unchanged_customer_not_duplicated(loader):
    incoming = pd.DataFrame([
        ["C1", "Bob", "Smith", "bob@x.com", "+1415", "94105", "CA", "shopify"],
    ], columns=CUSTOMER_COLUMNS)
    loader.upsert_scd2_customers(incoming, as_of=dt.date(2024, 1, 1))
    loader.upsert_scd2_customers(incoming, as_of=dt.date(2024, 2, 1))

    result = loader.conn.execute("SELECT * FROM dim_customers").fetchdf()
    assert len(result) == 1


def test_scd2_changed_customer_expires_old_row_and_inserts_new(loader):
    initial = pd.DataFrame([
        ["C1", "Bob", "Smith", "bob@x.com", "+1415", "94105", "CA", "shopify"],
    ], columns=CUSTOMER_COLUMNS)
    loader.upsert_scd2_customers(initial, as_of=dt.date(2024, 1, 1))

    changed = pd.DataFrame([
        ["C1", "Bob", "Smith", "bob-new@x.com", "+1415", "94105", "CA", "shopify"],
    ], columns=CUSTOMER_COLUMNS)
    loader.upsert_scd2_customers(changed, as_of=dt.date(2024, 2, 1))

    result = loader.conn.execute("SELECT * FROM dim_customers ORDER BY effective_date").fetchdf()
    assert len(result) == 2
    assert result.iloc[0]["is_current"] == False  # noqa: E712
    assert result.iloc[0]["expiration_date"] == pd.Timestamp(2024, 2, 1)
    assert result.iloc[1]["is_current"] == True  # noqa: E712
    assert result.iloc[1]["email"] == "bob-new@x.com"


def test_upsert_empty_dataframe_is_noop(loader):
    loader.upsert("fact_orders", _fact_orders_df([]))
    result = loader.conn.execute("SELECT * FROM fact_orders").fetchdf()
    assert result.empty
