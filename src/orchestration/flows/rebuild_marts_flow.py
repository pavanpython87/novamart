"""Mart-rebuild flow: recomputes pre-computed aggregation tables from the
serving warehouse's stg_orders, without re-ingesting or re-cleaning.

Scope selects which marts to rebuild (mirroring the GitHub Actions
cadence):
  - daily:  revenue + channel marts (rebuilt after every daily pipeline run)
  - weekly: customer/product/inventory marts (rebuilt on the weekly schedule)
  - all:    every mart (used by full refresh and manual rebuilds)

Reads/writes BigQuery (in addition to DuckDB) when WAREHOUSE_BACKEND is
bigquery/both, same as main_pipeline. This matters most for the weekly
schedule: it runs in its own GitHub Actions job with no prior ingest step,
so the local DuckDB file is empty on that fresh runner — BigQuery is the
only place stg_orders actually persists across separate scheduled jobs.
"""

from __future__ import annotations

import pandas as pd
from prefect import flow

from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.config import load_pipeline_config
from src.orchestration.flows.main_pipeline import _build_bigquery_loader
from src.orchestration.tasks.load_tasks import write_bigquery_tables, write_duckdb_tables
from src.transform.mart_builder import build_all_marts

MART_TABLES = [
    "mart_revenue_daily",
    "mart_customer_ltv",
    "mart_product_performance",
    "mart_inventory_health",
    "mart_channel_performance",
]

SCOPE_TABLES = {
    "daily": ["mart_revenue_daily", "mart_channel_performance"],
    "weekly": ["mart_customer_ltv", "mart_product_performance", "mart_inventory_health"],
    "all": MART_TABLES,
}


def _read_stg_orders(duckdb_loader: DuckDBLoader, bigquery_loader) -> pd.DataFrame:
    """Prefers BigQuery (persists across separate scheduled jobs) and falls
    back to the local DuckDB serving file, mirroring dashboard/db_connector
    .py's backend fallback."""
    if bigquery_loader is not None:
        bq_orders = bigquery_loader.read_dataframe("stg_orders")
        if not bq_orders.empty:
            return bq_orders
    try:
        return duckdb_loader.conn.execute("SELECT * FROM stg_orders").fetchdf()
    except Exception:
        return pd.DataFrame()


@flow(name="rebuild-marts")
def rebuild_marts_flow(
    serving_db: str = "data/serving/novamart_serving.duckdb",
    scope: str = "all",
    sources_config: str = "config/pipeline_config.yaml",
) -> dict:
    """Reads stg_orders back out of the serving warehouse, rebuilds every
    mart, and writes the requested scope back. Returns per-mart row counts
    and the tables actually written."""
    if scope not in SCOPE_TABLES:
        raise ValueError(f"Unknown scope {scope!r}; expected one of {sorted(SCOPE_TABLES)}")

    config = load_pipeline_config(sources_config)
    bigquery_loader = _build_bigquery_loader(config)

    loader = DuckDBLoader(serving_db)
    loader.create_schema()
    orders = _read_stg_orders(loader, bigquery_loader)

    all_marts = build_all_marts(orders) if not orders.empty else {}
    scope_marts = {
        name: all_marts[name]
        for name in SCOPE_TABLES[scope]
        if name in all_marts
    }
    written = write_duckdb_tables(loader, scope_marts)
    bq_written = write_bigquery_tables(bigquery_loader, scope_marts) if bigquery_loader else []
    loader.close()

    return {
        "scope": scope,
        "order_row_count": len(orders),
        "mart_row_counts": {name: len(df) for name, df in scope_marts.items()},
        "tables_written": written,
        "bigquery_tables_written": bq_written,
    }
