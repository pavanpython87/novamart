import datetime as dt
from unittest.mock import MagicMock

import yaml

from src.orchestration.flows import main_pipeline as main_pipeline_module
from src.orchestration.flows.main_pipeline import main_pipeline
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


def test_main_pipeline_ingests_and_builds_marts(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    result = main_pipeline.fn(
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        sources_config=config_path,
        batch_id="test-batch-1",
    )

    assert result["batch_id"] == "test-batch-1"
    assert sum(result["source_row_counts"].values()) > 0
    assert result["order_row_count"] > 0
    assert "stg_orders" in result["tables_written"]
    assert "mart_revenue_daily" in result["tables_written"]
    # No warehouse.backend section in the test config and no BQ_PROJECT_ID
    # in the test environment, so this must fall back to duckdb-only.
    assert result["warehouse_backend"] == "duckdb"
    assert result["bigquery_tables_written"] == []


def test_main_pipeline_writes_bigquery_when_configured(tmp_path, monkeypatch):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    fake_bigquery_loader = MagicMock()
    monkeypatch.setattr(
        main_pipeline_module, "_build_bigquery_loader", lambda config: fake_bigquery_loader,
    )
    monkeypatch.setenv("WAREHOUSE_BACKEND", "both")

    result = main_pipeline.fn(
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        sources_config=config_path,
        batch_id="test-batch-bq",
    )

    assert result["warehouse_backend"] == "both"
    assert "stg_orders" in result["bigquery_tables_written"]
    assert "mart_revenue_daily" in result["bigquery_tables_written"]
    assert fake_bigquery_loader.load_dataframe.call_count > 0


def test_main_pipeline_no_data_returns_empty_summary(tmp_path):
    incoming_dir = tmp_path / "incoming"
    for name in ("shopify", "amazon", "pos"):
        (incoming_dir / name).mkdir(parents=True)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    result = main_pipeline.fn(
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        sources_config=config_path,
    )

    assert sum(result["source_row_counts"].values()) == 0
    assert result["order_row_count"] == 0
    assert result["tables_written"] == []
