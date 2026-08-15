"""Orchestrates loading to DuckDB (always) and BigQuery (when configured),
per PROJECT_PLAN.md 5.7's dual-destination loading strategy.

Config toggle mirrors config/pipeline_config.yaml's warehouse.backend:
"duckdb" | "bigquery" | "both".
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.load.duckdb_loader import DuckDBLoader

VALID_BACKENDS = {"duckdb", "bigquery", "both"}


class DualLoader:
    def __init__(self, duckdb_loader: DuckDBLoader, bigquery_loader=None, backend: str = "duckdb"):
        if backend not in VALID_BACKENDS:
            raise ValueError(f"Unknown backend: {backend}")
        if backend in ("bigquery", "both") and bigquery_loader is None:
            raise ValueError(f"bigquery_loader is required for backend={backend!r}")

        self.duckdb_loader = duckdb_loader
        self.bigquery_loader = bigquery_loader
        self.backend = backend

    def load(self, table_name: str, df, scd2: bool = False) -> dict[str, str]:
        """Loads df into table_name on every destination this backend
        targets. Returns a dict of destination -> status, so callers can
        report which warehouses were actually written to."""
        results: dict[str, str] = {}

        if self.backend in ("duckdb", "both"):
            if scd2:
                self.duckdb_loader.upsert_scd2_customers(df)
            else:
                self.duckdb_loader.upsert(table_name, df)
            results["duckdb"] = "loaded"

        if self.backend in ("bigquery", "both"):
            self.bigquery_loader.upsert(table_name, df)
            results["bigquery"] = "loaded"

        return results


def build_dual_loader(config_path: str = "config/pipeline_config.yaml", bigquery_loader=None) -> DualLoader:
    """Factory reading warehouse.backend + serving_db from pipeline_config.yaml.

    A pre-built bigquery_loader must be supplied when the configured
    backend requires BigQuery, since constructing a real
    google.cloud.bigquery.Client needs credentials this factory has no
    business owning.
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    warehouse = config.get("warehouse", {})
    backend = warehouse.get("backend", "duckdb")
    serving_db = warehouse.get("serving_db", "data/serving/novamart_serving.duckdb")

    Path(serving_db).parent.mkdir(parents=True, exist_ok=True)
    duckdb_loader = DuckDBLoader(serving_db)
    duckdb_loader.create_schema()

    return DualLoader(duckdb_loader, bigquery_loader=bigquery_loader, backend=backend)
