"""Full-refresh flow: reprocess everything from scratch.

Resets the incremental tracker (so every file is re-ingested), deletes the
serving warehouse + quarantine databases (so they're rebuilt empty), and
optionally resets profiling baselines before running the full pipeline
once. Matches PROJECT_PLAN.md 3.2's FULL REFRESH mode.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from prefect import flow

from src.monitoring.run_logger import RunLogger
from src.orchestration.flows.main_pipeline import main_pipeline


def _delete_if_exists(path: str | Path) -> None:
    path = Path(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


@flow(name="full-refresh")
def full_refresh_flow(
    sources_config: str = "config/pipeline_config.yaml",
    tracker_db: str = "data/landing/novamart_tracker.db",
    baseline_dir: str = "data/landing/baselines",
    quarantine_db: str = "data/quarantine/novamart_quarantine.db",
    serving_db: str = "data/serving/novamart_serving.duckdb",
    run_log_path: str = "data/logs/run_history.jsonl",
    reset_baselines: bool = True,
    batch_id: str | None = None,
) -> dict:
    """Truncates all local state and reprocesses every file in
    data/incoming/. Returns the main_pipeline summary plus the state that
    was reset."""
    reset = {
        "tracker_db": Path(tracker_db).exists(),
        "baseline_dir": reset_baselines and Path(baseline_dir).exists(),
        "quarantine_db": Path(quarantine_db).exists(),
        "serving_db": Path(serving_db).exists(),
    }

    _delete_if_exists(tracker_db)
    _delete_if_exists(quarantine_db)
    _delete_if_exists(serving_db)
    if reset_baselines:
        _delete_if_exists(baseline_dir)

    result = main_pipeline(
        tracker_db=tracker_db,
        baseline_dir=baseline_dir,
        quarantine_db=quarantine_db,
        serving_db=serving_db,
        sources_config=sources_config,
        batch_id=batch_id,
    )

    RunLogger(run_log_path).log_run({
        "mode": "full-refresh",
        "batch_id": result["batch_id"],
        "reset": reset,
        "source_row_counts": result["source_row_counts"],
        "order_row_count": result["order_row_count"],
        "tables_written": result["tables_written"],
    })
    result["reset"] = reset
    return result
