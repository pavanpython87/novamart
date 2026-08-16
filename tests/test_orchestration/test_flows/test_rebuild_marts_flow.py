import datetime as dt

import yaml

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


def test_rebuild_marts_rejects_unknown_scope():
    try:
        rebuild_marts_flow.fn(serving_db=":memory:", scope="nope")
    except ValueError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown scope")
