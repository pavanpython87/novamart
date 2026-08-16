import datetime as dt

import yaml

from src.orchestration.flows.backfill_flow import backfill_flow


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


def test_backfill_flow_simulates_and_processes_range(tmp_path):
    incoming_dir = tmp_path / "incoming"
    config_path = _write_pipeline_config(tmp_path, incoming_dir)

    result = backfill_flow.fn(
        dt.date(2024, 1, 1), dt.date(2024, 1, 1),
        incoming_dir=incoming_dir,
        sources_config=config_path,
        tracker_db=str(tmp_path / "tracker.db"),
        baseline_dir=str(tmp_path / "baselines"),
        quarantine_db=str(tmp_path / "quarantine.db"),
        serving_db=str(tmp_path / "serving.duckdb"),
        run_log_path=str(tmp_path / "run_history.jsonl"),
        seed=1,
        chaos_level=0.0,
        batch_id="backfill-1",
    )

    assert result["batch_id"] == "backfill-1"
    assert sum(result["simulation"].values()) > 0
    assert result["order_row_count"] > 0
    assert "stg_orders" in result["tables_written"]


def test_backfill_flow_rejects_inverted_range():
    try:
        backfill_flow.fn(dt.date(2024, 1, 2), dt.date(2024, 1, 1))
    except ValueError as exc:
        assert "start_date" in str(exc)
    else:
        raise AssertionError("expected ValueError for inverted range")
