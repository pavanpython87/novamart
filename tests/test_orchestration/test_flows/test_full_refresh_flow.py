import datetime as dt

import yaml

from src.orchestration.flows.full_refresh_flow import full_refresh_flow
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


def test_full_refresh_resets_state_and_reprocesses(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1, chaos_level=0.0)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    common = dict(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
    )
    run_log_path = str(tmp_path / "run_history.jsonl")

    first = main_pipeline.fn(**common, batch_id="first")
    assert first["order_row_count"] > 0

    result = full_refresh_flow.fn(**common, run_log_path=run_log_path, batch_id="refresh")

    assert result["order_row_count"] == first["order_row_count"]
    assert result["order_row_count"] > 0
    assert "stg_orders" in result["tables_written"]
    # The tracker + warehouse existed from the first run, so the reset flags
    # must record that they were cleared.
    assert result["reset"]["tracker_db"] is True
    assert result["reset"]["serving_db"] is True
