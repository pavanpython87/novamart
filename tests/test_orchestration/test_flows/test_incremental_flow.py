import datetime as dt

import yaml

from src.orchestration.flows.incremental_flow import incremental_flow
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


def test_incremental_flow_runs_pipeline_and_logs(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 1), incoming_dir, seed=1, chaos_level=0.0)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    result = incremental_flow.fn(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        run_log_path=str(tmp_path / "run_history.jsonl"),
        quality_log_path=str(tmp_path / "quality_trend.jsonl"),
        batch_id="inc-1",
    )

    assert result["batch_id"] == "inc-1"
    assert result["order_row_count"] > 0
    assert "stg_orders" in result["tables_written"]
    assert (tmp_path / "run_history.jsonl").exists()
    assert (tmp_path / "quality_trend.jsonl").exists()


def test_incremental_flow_no_data(tmp_path):
    incoming_dir = tmp_path / "incoming"
    for name in ("shopify", "amazon", "pos"):
        (incoming_dir / name).mkdir(parents=True)
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    result = incremental_flow.fn(
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        run_log_path=str(tmp_path / "run_history.jsonl"),
        quality_log_path=str(tmp_path / "quality_trend.jsonl"),
    )

    assert result["order_row_count"] == 0
    assert result["tables_written"] == []
