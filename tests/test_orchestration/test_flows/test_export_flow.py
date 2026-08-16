import datetime as dt

import yaml

from src.orchestration.flows.export_flow import export_flow
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


def test_export_flow_writes_mart_files(tmp_path):
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

    result = export_flow.fn(serving_db=serving_db, export_dir=str(tmp_path / "exports"),
                            formats=("csv",))

    assert result["exported"]
    assert (tmp_path / "exports" / "mart_revenue_daily.csv").exists()


def test_export_flow_empty_warehouse_returns_empty(tmp_path):
    result = export_flow.fn(serving_db=str(tmp_path / "empty.duckdb"),
                            export_dir=str(tmp_path / "exports"))
    assert result == {"exported": {}}
