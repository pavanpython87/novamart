"""Warehouse connection layer for the Streamlit dashboard.

Reads from BigQuery by default (production analytical warehouse) and falls
back to the local DuckDB serving warehouse (offline / no-credentials mode),
per PROJECT_PLAN.md 5.7's dual-destination strategy.

Both backends expose the same query API, and query results are cached with
Streamlit's cache_data so the dashboard stays sub-second even on repeated
filter changes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

DEFAULT_DUCKDB = "data/serving/novamart_serving.duckdb"


@st.cache_resource(show_spinner=False)
def _bigquery_client(project_id: str):
    from google.cloud import bigquery

    return bigquery.Client(project=project_id)


def _resolve_backend() -> str:
    """Decides which warehouse the dashboard reads from.

    "both" means "prefer BigQuery, DuckDB otherwise"; "bigquery" without
    credentials falls back to DuckDB so the dashboard still renders locally.
    """
    configured = os.environ.get("WAREHOUSE_BACKEND", "duckdb").strip().lower()
    if configured == "bigquery":
        if os.environ.get("BQ_PROJECT_ID") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return "bigquery"
        st.warning("WAREHOUSE_BACKEND=bigquery but no credentials found — falling back to DuckDB.")
        return "duckdb"
    if configured == "both":
        if os.environ.get("BQ_PROJECT_ID") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return "bigquery"
        return "duckdb"
    return "duckdb"


@st.cache_data(ttl=60, show_spinner=False)
def _cached_query_duckdb(db_path: str, sql: str) -> pd.DataFrame:
    """Opens a fresh read-only connection per query so the dashboard always
    sees the latest pipeline output (and never holds a lock on Windows)."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    import duckdb

    conn = duckdb.connect(db_path, read_only=True)
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_query_bigquery(project_id: str, dataset: str, sql: str) -> pd.DataFrame:
    client = _bigquery_client(project_id)
    return client.query(sql).to_dataframe()


class WarehouseClient:
    def __init__(self, backend: str | None = None):
        self.backend = backend or _resolve_backend()
        if self.backend == "bigquery":
            self.project_id = os.environ.get("BQ_PROJECT_ID", "")
            self.dataset = os.environ.get("BQ_DATASET", "novamart")
            if not self.project_id:
                raise RuntimeError("BQ_PROJECT_ID must be set for the BigQuery backend")
        else:
            self.db_path = os.environ.get("SERVING_DB", DEFAULT_DUCKDB)

    # -- metadata -------------------------------------------------------

    def list_tables(self) -> list[str]:
        if self.backend == "bigquery":
            client = _bigquery_client(self.project_id)
            return [t.table_id for t in client.list_tables(self.dataset)]
        if not Path(self.db_path).exists():
            return []
        import duckdb

        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def table_exists(self, table: str) -> bool:
        return table in self.list_tables()

    # -- querying -------------------------------------------------------

    def query(self, sql: str) -> pd.DataFrame:
        if self.backend == "bigquery":
            return _cached_query_bigquery(self.project_id, self.dataset, sql)
        return _cached_query_duckdb(self.db_path, sql)

    def query_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        """SELECTs all rows from a known table, with an optional LIMIT.
        Returns an empty DataFrame if the table doesn't exist."""
        if not self.table_exists(table):
            return pd.DataFrame()
        sql = f"SELECT * FROM {table}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.query(sql)

    # -- SQL dialect helpers -------------------------------------------

    def date_cast(self, column: str) -> str:
        """SQL expression casting `column` to a DATE. DuckDB and BigQuery
        use different safe-cast spellings, so callers go through here."""
        if self.backend == "bigquery":
            return f"SAFE_CAST({column} AS DATE)"
        return f"TRY_CAST({column} AS DATE)"

    def channel_filter(self, channels: list[str], column: str = "channel") -> str:
        quoted = ", ".join(f"'{c}'" for c in channels)
        return f"{column} IN ({quoted})"


@st.cache_resource(show_spinner=False)
def get_client() -> WarehouseClient:
    """Process-wide cached warehouse client (one per Streamlit session)."""
    return WarehouseClient()
