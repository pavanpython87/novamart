import datetime as dt
import random

import pytest

from src.ingestion.sqlite_connector import SQLiteConnector
from src.simulator.product_simulator import generate_product_catalog
from src.simulator.universe import Universe


def test_sqlite_connector_reads_full_table(tmp_path):
    universe = Universe(seed=1)
    path = generate_product_catalog(universe, dt.date(2024, 3, 1), tmp_path,
                                      rng=random.Random(1))
    conn = SQLiteConnector(path, table="products")
    conn.connect()
    df = conn.extract()
    assert len(df) > 0
    assert "product_id" in df.columns


def test_sqlite_connector_custom_query(tmp_path):
    universe = Universe(seed=1)
    path = generate_product_catalog(universe, dt.date(2024, 3, 1), tmp_path,
                                      rng=random.Random(1))
    conn = SQLiteConnector(path, query="SELECT product_id, is_active FROM products WHERE is_active = 1")
    conn.connect()
    df = conn.extract()
    assert set(df.columns) == {"product_id", "is_active"}
    assert (df["is_active"] == 1).all()


def test_sqlite_connector_hwm_filtering(tmp_path):
    universe = Universe(seed=1)
    path = generate_product_catalog(universe, dt.date(2024, 3, 1), tmp_path,
                                      rng=random.Random(1))
    full = SQLiteConnector(path, table="products")
    full.connect()
    full_df = full.extract()
    mid_id = sorted(full_df["product_id"])[len(full_df) // 2]

    conn = SQLiteConnector(path, table="products", hwm_column="product_id", hwm_value=mid_id)
    conn.connect()
    df = conn.extract()
    assert all(pid > mid_id for pid in df["product_id"])
    assert conn.max_hwm_value == df["product_id"].max()


def test_sqlite_connector_requires_table_or_query(tmp_path):
    with pytest.raises(ValueError):
        SQLiteConnector(tmp_path / "x.db")


def test_sqlite_connector_missing_file_raises(tmp_path):
    conn = SQLiteConnector(tmp_path / "nope.db", table="products")
    with pytest.raises(FileNotFoundError):
        conn.connect()
