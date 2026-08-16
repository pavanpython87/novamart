"""Backfill flow: (re)generate and process a historical date range.

Used when transformation logic was updated and a window of history needs
reprocessing (PROJECT_PLAN.md 3.2's BACKFILL RUN). Simulates the date
range into data/incoming/, then runs the incremental pipeline — the file
registry's SHA-256 check means files already identical to a previous run
are skipped, while changed/regenerated files are re-ingested.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from prefect import flow

from src.monitoring.run_logger import RunLogger
from src.orchestration.flows.main_pipeline import main_pipeline
from src.orchestration.tasks.simulate_tasks import simulate_data


@flow(name="backfill")
def backfill_flow(
    start_date: dt.date,
    end_date: dt.date,
    incoming_dir: str | Path = "data/incoming",
    sources_config: str = "config/pipeline_config.yaml",
    tracker_db: str = "data/landing/novamart_tracker.db",
    baseline_dir: str = "data/landing/baselines",
    quarantine_db: str = "data/quarantine/novamart_quarantine.db",
    serving_db: str = "data/serving/novamart_serving.duckdb",
    run_log_path: str = "data/logs/run_history.jsonl",
    seed: int = 42,
    chaos_level: float = 1.0,
    batch_id: str | None = None,
) -> dict:
    """Simulates [start_date, end_date] and processes it through the full
    pipeline. Returns the main_pipeline summary plus the simulation
    summary."""
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    simulation = simulate_data(start_date, end_date, output_dir=incoming_dir,
                               seed=seed, chaos_level=chaos_level)

    result = main_pipeline(
        tracker_db=tracker_db,
        baseline_dir=baseline_dir,
        quarantine_db=quarantine_db,
        serving_db=serving_db,
        sources_config=sources_config,
        batch_id=batch_id,
    )

    RunLogger(run_log_path).log_run({
        "mode": "backfill",
        "batch_id": result["batch_id"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "files_written": simulation,
        "source_row_counts": result["source_row_counts"],
        "order_row_count": result["order_row_count"],
        "tables_written": result["tables_written"],
    })
    result["simulation"] = simulation
    return result
