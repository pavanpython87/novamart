"""Phase 5 day-18 integration test: simulate a week of data, run the
pipeline daily, and verify idempotent catch-up (PROJECT_PLAN.md 3.2 /
3.4).

Idempotency is the pipeline's most important property: whether the same
files are processed as N separate runs or one catch-up run, the warehouse
ends up in the same state. These tests encode that contract.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import yaml

from src.load.duckdb_loader import DuckDBLoader
from src.orchestration.flows.main_pipeline import main_pipeline
from src.simulator.simulator_main import generate_range

ORDER_SOURCES = ("shopify", "amazon", "pos")


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


def _fresh_state_paths(tmp_path):
    return {
        "tracker_db": str(tmp_path / "tracker.db"),
        "baseline_dir": str(tmp_path / "baselines"),
        "quarantine_db": str(tmp_path / "quarantine.db"),
        "serving_db": str(tmp_path / "serving.duckdb"),
    }


def _run(tmp_path, incoming_dir, batch_id=None):
    return main_pipeline.fn(
        sources_config=_write_pipeline_config(tmp_path, incoming_dir),
        batch_id=batch_id,
        **_fresh_state_paths(tmp_path),
    )


def _serving_order_count(serving_db: str) -> int:
    loader = DuckDBLoader(serving_db)
    loader.create_schema()
    try:
        return loader.conn.execute("SELECT COUNT(*) AS n FROM stg_orders").fetchone()[0]
    finally:
        loader.close()


def _wipe_local_state(tmp_path):
    for path in _fresh_state_paths(tmp_path).values():
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def _move_files_for_date(incoming_dir: Path, date_str: str, staging: Path) -> None:
    """Moves every generated file whose name contains `date_str`
    (YYYYMMDD) to a mirrored location under `staging`."""
    for file in incoming_dir.rglob(f"*{date_str}*"):
        if file.is_file():
            rel = file.relative_to(incoming_dir)
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file), str(dest))


def test_seven_day_simulation_is_idempotent_on_rerun(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 7), incoming_dir,
                   seed=7, chaos_level=0.0)

    first = _run(tmp_path, incoming_dir, batch_id="day-1")
    first_count = first["order_row_count"]
    assert first_count > 0
    serving_db = _fresh_state_paths(tmp_path)["serving_db"]
    assert _serving_order_count(serving_db) == first_count

    # A second run finds no new/changed files: zero new source rows, and the
    # warehouse is left untouched (same stored row count).
    second = _run(tmp_path, incoming_dir, batch_id="day-2")
    assert second["order_row_count"] == 0
    assert sum(second["source_row_counts"].values()) == 0
    assert _serving_order_count(serving_db) == first_count


def test_catch_up_equivalence_three_days(tmp_path):
    incoming_dir = tmp_path / "incoming"
    generate_range(dt.date(2024, 1, 1), dt.date(2024, 1, 3), incoming_dir,
                   seed=3, chaos_level=0.0)
    serving_db = _fresh_state_paths(tmp_path)["serving_db"]

    # Baseline: process all three days in a single run.
    _run(tmp_path, incoming_dir, batch_id="full")
    full_count = _serving_order_count(serving_db)
    assert full_count > 0

    # Reset local state and hold day 3 aside to simulate a partial week.
    _wipe_local_state(tmp_path)
    staging = tmp_path / "staging"
    _move_files_for_date(incoming_dir, "20240103", staging)

    _run(tmp_path, incoming_dir, batch_id="days-1-2")
    partial_count = _serving_order_count(serving_db)
    assert 0 < partial_count < full_count

    # "Catch up": day 3's files arrive on the next run.
    for file in staging.rglob("*"):
        if file.is_file():
            rel = file.relative_to(staging)
            dest = incoming_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file), str(dest))

    caught_up = _run(tmp_path, incoming_dir, batch_id="catch-up")
    assert caught_up["order_row_count"] > 0
    assert _serving_order_count(serving_db) == full_count
