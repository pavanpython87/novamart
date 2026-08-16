"""Mart-rebuild flow: recomputes pre-computed aggregation tables from the
serving warehouse's stg_orders, without re-ingesting or re-cleaning.

Scope selects which marts to rebuild (mirroring the GitHub Actions
cadence):
  - daily:  revenue + channel marts (rebuilt after every daily pipeline run)
  - weekly: customer/product/inventory marts (rebuilt on the weekly schedule)
  - all:    every mart (used by full refresh and manual rebuilds)
"""

from __future__ import annotations

import pandas as pd
from prefect import flow

from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.tasks.load_tasks import write_duckdb_tables
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


@flow(name="rebuild-marts")
def rebuild_marts_flow(
    serving_db: str = "data/serving/novamart_serving.duckdb",
    scope: str = "all",
) -> dict:
    """Reads stg_orders back out of the serving warehouse, rebuilds every
    mart, and writes the requested scope back. Returns per-mart row counts
    and the tables actually written."""
    if scope not in SCOPE_TABLES:
        raise ValueError(f"Unknown scope {scope!r}; expected one of {sorted(SCOPE_TABLES)}")

    loader = DuckDBLoader(serving_db)
    loader.create_schema()
    try:
        orders = loader.conn.execute("SELECT * FROM stg_orders").fetchdf()
    except Exception:
        orders = pd.DataFrame()

    all_marts = build_all_marts(orders) if not orders.empty else {}
    scope_marts = {
        name: all_marts[name]
        for name in SCOPE_TABLES[scope]
        if name in all_marts
    }
    written = write_duckdb_tables(loader, scope_marts)
    loader.close()

    return {
        "scope": scope,
        "order_row_count": len(orders),
        "mart_row_counts": {name: len(df) for name, df in scope_marts.items()},
        "tables_written": written,
    }
