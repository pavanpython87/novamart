"""Tests the SKU-mapping integration: when the product catalog source is
configured, stg_orders.product_key resolves to the unified product_id (not
the raw channel SKU/ASIN), and the inventory marts build on that shared
identity."""

from __future__ import annotations

import datetime as dt
import sqlite3

import yaml

from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.flows.main_pipeline import main_pipeline
from src.simulator.simulator_main import generate_range


def _write_config(tmp_path, incoming_dir) -> str:
    config = {
        "sources": {
            "shopify": {"format": "csv", "incoming_dir": str(incoming_dir / "shopify"),
                        "incremental_mode": "file_registry"},
            "amazon": {"format": "xlsx", "incoming_dir": str(incoming_dir / "amazon"),
                       "incremental_mode": "file_registry"},
            "pos": {"format": "json", "incoming_dir": str(incoming_dir / "pos"),
                    "incremental_mode": "file_registry"},
            "products": {"format": "sqlite", "incoming_dir": str(incoming_dir / "products"),
                         "incremental_mode": "high_water_mark", "hwm_column": "updated_at"},
        },
    }
    path = tmp_path / "pipeline_config.yaml"
    path.write_text(yaml.dump(config), encoding="utf-8")
    return str(path)


def test_main_pipeline_maps_orders_to_unified_product_ids(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir,
                   seed=1, chaos_level=0.0)
    serving_db = str(tmp_path / "serving.duckdb")

    result = main_pipeline.fn(
        sources_config=_write_config(tmp_path, incoming_dir),
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=serving_db,
        batch_id="mapping-test",
    )

    assert result["order_row_count"] > 0
    assert "fact_inventory_daily" in result["tables_written"]
    assert "mart_inventory_health" in result["tables_written"]

    # Canonical product ids straight from the generated catalog.
    catalog_file = next((incoming_dir / "products").glob("*.db"))
    conn = sqlite3.connect(catalog_file)
    product_ids = {
        row[0] for row in conn.execute(
            "SELECT product_id FROM products WHERE product_id NOT LIKE '%-DUP'"
        )
    }
    conn.close()

    loader = DuckDBLoader(serving_db)
    loader.create_schema()
    mapped = loader.conn.execute(
        "SELECT channel, product_key FROM stg_orders WHERE channel IN ('shopify', 'amazon')"
    ).fetchdf()
    pos = loader.conn.execute(
        "SELECT product_key FROM stg_orders WHERE channel = 'pos'"
    ).fetchdf()
    loader.close()

    assert mapped["product_key"].notna().all()
    assert set(mapped["product_key"]) <= product_ids

    # POS line items are exploded and SKU-mapped to the same unified ids.
    assert not pos.empty
    assert pos["product_key"].notna().all()
    assert set(pos["product_key"]) <= product_ids
