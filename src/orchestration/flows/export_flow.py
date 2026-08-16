"""Export flow: reads the mart tables out of the serving warehouse and
writes them to data/exports/ as CSV/Excel/PDF reports (see
src.load.export_manager and PROJECT_PLAN.md's Export/Delivery layer).
"""

from __future__ import annotations

import pandas as pd
from prefect import flow

from src.load.duckdb_loader import DuckDBLoader
from src.load.export_manager import export_marts
from src.orchestration.flows.rebuild_marts_flow import MART_TABLES


@flow(name="export-reports")
def export_flow(
    serving_db: str = "data/serving/novamart_serving.duckdb",
    export_dir: str = "data/exports",
    formats: tuple[str, ...] = ("csv", "excel"),
) -> dict:
    """Reads every populated mart table from the serving warehouse and
    exports it in the requested formats. Returns a mart -> file paths map."""
    loader = DuckDBLoader(serving_db)
    loader.create_schema()

    marts: dict[str, pd.DataFrame] = {}
    for table in MART_TABLES:
        try:
            df = loader.conn.execute(f"SELECT * FROM {table}").fetchdf()
        except Exception:
            continue
        if not df.empty:
            marts[table] = df
    loader.close()

    if not marts:
        return {"exported": {}}

    return {"exported": export_marts(marts, export_dir, formats=formats)}
