"""Tests for the dashboard warehouse connection layer (DuckDB path)."""

from __future__ import annotations

import duckdb
import pytest

from dashboard.db_connector import WarehouseClient, _resolve_backend


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = tmp_path / "serving.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE t AS SELECT 1 AS a UNION ALL SELECT 2 AS a")
    conn.close()

    monkeypatch.setenv("SERVING_DB", str(db_path))
    monkeypatch.setenv("WAREHOUSE_BACKEND", "duckdb")
    return WarehouseClient(backend="duckdb")


def test_list_tables(client):
    assert client.list_tables() == ["t"]
    assert client.table_exists("t") is True
    assert client.table_exists("missing") is False


def test_query_returns_rows(client):
    df = client.query("SELECT * FROM t ORDER BY a")
    assert df["a"].tolist() == [1, 2]


def test_query_table_missing_returns_empty(client):
    assert client.query_table("missing").empty


def test_dialect_helpers(client):
    assert client.date_cast("order_date") == "TRY_CAST(order_date AS DATE)"
    assert client.channel_filter(["shopify", "amazon"]) == "channel IN ('shopify', 'amazon')"


def test_resolve_backend_prefers_duckdb(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_BACKEND", "duckdb")
    monkeypatch.delenv("BQ_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert _resolve_backend() == "duckdb"


def test_resolve_backend_bigquery_requires_credentials(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_BACKEND", "bigquery")
    monkeypatch.delenv("BQ_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert _resolve_backend() == "duckdb"

    monkeypatch.setenv("BQ_PROJECT_ID", "my-project")
    assert _resolve_backend() == "bigquery"
