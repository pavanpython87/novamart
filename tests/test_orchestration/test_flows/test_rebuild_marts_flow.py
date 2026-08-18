import datetime as dt
from unittest.mock import MagicMock

import pandas as pd
import yaml

from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.flows import rebuild_marts_flow as rebuild_marts_flow_module
from src.orchestration.flows.main_pipeline import main_pipeline
from src.orchestration.flows.rebuild_marts_flow import SCOPE_TABLES, rebuild_marts_flow
from src.simulator.simulator_main import generate_range


def _write_pipeline_config(tmp_path, incoming_dir) -> str:
    config = {
        "sources": {
            "shopify": {"format": "csv", "incoming_dir": str(incoming_dir / "shopify"),
                        "incremental_mode": "file_registry"},
            "amazon": {"format": "xlsx", "incoming_dir": str(incoming_dir / "amazon"),
                       "incremental_mode": "file_registry"},
            "pos": {"format": "json", "incoming_dir": str(incoming_dir / "pos"),
                    "incremental_mode": "file_registry"},
        },
    }
    config_path = tmp_path / "pipeline_config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return str(config_path)


def test_rebuild_marts_rebuilds_scope_from_serving_warehouse(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1, chaos_level=0.0)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)
    serving_db = str(tmp_path / "serving.duckdb")

    main_pipeline.fn(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=serving_db,
    )

    result = rebuild_marts_flow.fn(serving_db=serving_db, scope="daily")

    assert result["order_row_count"] > 0
    assert set(result["tables_written"]) == set(SCOPE_TABLES["daily"])


def test_rebuild_marts_writes_bigquery_when_configured(tmp_path, monkeypatch):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1, chaos_level=0.0)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)
    serving_db = str(tmp_path / "serving.duckdb")

    main_pipeline.fn(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=serving_db,
    )

    fake_bigquery_loader = MagicMock()
    fake_bigquery_loader.read_dataframe.return_value = pd.DataFrame()
    monkeypatch.setattr(
        rebuild_marts_flow_module, "_build_bigquery_loader", lambda config: fake_bigquery_loader,
    )

    result = rebuild_marts_flow.fn(serving_db=serving_db, scope="daily")

    assert result["order_row_count"] > 0
    assert set(result["tables_written"]) == set(SCOPE_TABLES["daily"])
    assert set(result["bigquery_tables_written"]) == set(SCOPE_TABLES["daily"])
    assert fake_bigquery_loader.load_dataframe.call_count == len(SCOPE_TABLES["daily"])


def test_rebuild_marts_reads_from_bigquery_when_local_duckdb_is_empty(tmp_path, monkeypatch):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1, chaos_level=0.0)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)
    warm_serving_db = str(tmp_path / "warm_serving.duckdb")

    main_pipeline.fn(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=warm_serving_db,
    )
    warm_loader = DuckDBLoader(warm_serving_db)
    stg_orders = warm_loader.conn.execute("SELECT * FROM stg_orders").fetchdf()
    warm_loader.close()
    assert not stg_orders.empty

    fake_bigquery_loader = MagicMock()
    fake_bigquery_loader.read_dataframe.return_value = stg_orders
    monkeypatch.setattr(
        rebuild_marts_flow_module, "_build_bigquery_loader", lambda config: fake_bigquery_loader,
    )

    # Fresh, never-ingested-into serving_db path — simulates the weekly
    # GitHub Actions job's empty runner, which has no prior local state.
    fresh_serving_db = str(tmp_path / "fresh_serving.duckdb")
    result = rebuild_marts_flow.fn(serving_db=fresh_serving_db, scope="weekly")

    fake_bigquery_loader.read_dataframe.assert_called_once_with("stg_orders")
    assert result["order_row_count"] == len(stg_orders)
    # mart_inventory_health needs an inventory snapshot rebuild_marts_flow
    # doesn't have (only main_pipeline builds one) so it stays empty here —
    # what matters for this test is that BigQuery-sourced orders reached
    # the marts that don't need inventory data.
    assert "mart_customer_ltv" in result["tables_written"]
    assert "mart_product_performance" in result["tables_written"]


def test_rebuild_marts_rejects_unknown_scope():
    try:
        rebuild_marts_flow.fn(serving_db=":memory:", scope="nope")
    except ValueError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown scope")
