"""Loading tasks: writes star-schema tables via DualLoader, and writes
free-form staging/mart tables (which don't have a fixed schema_manager
DDL) straight to the local DuckDB connection.
"""

from __future__ import annotations

import pandas as pd
from prefect import task

from src.load.dual_loader import DualLoader
from src.load.duckdb_loader import DuckDBLoader


@task(name="load-table", retries=3, retry_delay_seconds=10)
def load_table(table_name: str, df: pd.DataFrame, dual_loader: DualLoader, scd2: bool = False) -> dict[str, str]:
    if df.empty:
        return {}
    return dual_loader.load(table_name, df, scd2=scd2)


@task(name="write-duckdb-tables", retries=3, retry_delay_seconds=10)
def write_duckdb_tables(duckdb_loader: DuckDBLoader, tables: dict[str, pd.DataFrame]) -> list[str]:
    """Replaces each named table with the given DataFrame's contents.
    Used for staging/mart tables that aren't part of the fixed star schema
    (see schema_manager.TABLE_SCHEMAS), so DuckDBLoader.upsert's
    fixed-primary-key logic doesn't apply."""
    written = []
    for name, df in tables.items():
        if df.empty:
            continue
        duckdb_loader.conn.register("_incoming_df", df)
        duckdb_loader.conn.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _incoming_df")
        duckdb_loader.conn.unregister("_incoming_df")
        written.append(name)
    return written
