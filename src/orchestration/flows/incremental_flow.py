"""Lightweight incremental run flow.

Wraps main_pipeline (which is already incremental — the file registry/HWM
skip already-seen data) with the monitoring layer Phase 5 adds: append the
run summary to run_history.jsonl, record each source's quality outcome to
quality_trend.jsonl, and dispatch any quality-gate alerts.
"""

from __future__ import annotations

from prefect import flow

from src.monitoring.alert_manager import AlertManager
from src.monitoring.quality_tracker import QualityTracker
from src.monitoring.run_logger import RunLogger
from src.orchestration.flows.main_pipeline import main_pipeline
from src.orchestration.tasks.notify_tasks import send_alerts


@flow(name="incremental-pipeline")
def incremental_flow(
    sources_config: str = "config/pipeline_config.yaml",
    tracker_db: str = "data/landing/novamart_tracker.db",
    baseline_dir: str = "data/landing/baselines",
    quarantine_db: str = "data/quarantine/novamart_quarantine.db",
    serving_db: str = "data/serving/novamart_serving.duckdb",
    run_log_path: str = "data/logs/run_history.jsonl",
    quality_log_path: str = "data/logs/quality_trend.jsonl",
    batch_id: str | None = None,
) -> dict:
    """Runs the pipeline incrementally and records the run for monitoring.

    Returns the main_pipeline summary, augmented with an `alerts` list and
    the number of alerts dispatched."""
    result = main_pipeline(
        tracker_db=tracker_db,
        baseline_dir=baseline_dir,
        quarantine_db=quarantine_db,
        serving_db=serving_db,
        sources_config=sources_config,
        batch_id=batch_id,
    )

    batch_id = result["batch_id"]

    run_logger = RunLogger(run_log_path)
    run_logger.log_run({
        "mode": "incremental",
        "batch_id": batch_id,
        "source_row_counts": result["source_row_counts"],
        "order_row_count": result["order_row_count"],
        "tables_written": result["tables_written"],
    })

    quality_tracker = QualityTracker(quality_log_path)
    alert_manager = AlertManager()
    alerts: list[dict] = []
    for source, scorecard in result.get("quality", {}).items():
        quality_tracker.record_scorecard(batch_id, source, scorecard)
        alerts.extend(alert_manager.evaluate_scorecard(source, scorecard))

    sent = send_alerts(alerts)
    result["alerts"] = alerts
    result["alerts_sent"] = sent
    return result
