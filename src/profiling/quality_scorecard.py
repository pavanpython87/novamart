"""Scores a batch PASS/WARN/FAIL against config/pipeline_config.yaml's
quality_gate_thresholds, using drift_detector's schema + statistical
drift output.

PASS -> batch proceeds to staging
WARN -> batch proceeds + alert logged
FAIL -> batch quarantined + alert logged (pipeline continues with other sources)
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.profiling.drift_detector import detect_drift

DEFAULT_CONFIG_PATH = Path("config/pipeline_config.yaml")

DEFAULT_THRESHOLDS = {
    "null_pct_spike_warn": 20,
    "row_count_drop_fail_pct": 50,
    "new_column_action": "log_and_alert",
    "missing_column_action": "fail",
    "type_change_action": "warn",
}


def load_thresholds(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {**DEFAULT_THRESHOLDS, **raw.get("quality_gate_thresholds", {})}


def score_batch(current: dict, baseline: dict | None, thresholds: dict | None = None) -> dict:
    """Returns {"outcome": "PASS"|"WARN"|"FAIL", "reasons": [...], "drift": {...}}.

    A missing baseline (first-ever run for a source) always PASSes — there's
    nothing to drift against yet."""
    thresholds = thresholds or DEFAULT_THRESHOLDS
    if baseline is None:
        return {"outcome": "PASS", "reasons": ["no baseline yet — first run for this source"],
                "drift": None}

    drift = detect_drift(current, baseline)
    reasons: list[str] = []
    outcome = "PASS"

    if drift["missing_columns"] and thresholds["missing_column_action"] == "fail":
        outcome = "FAIL"
        reasons.append(f"missing columns: {drift['missing_columns']}")

    pct_change = drift["row_count_pct_change"]
    if pct_change is not None and pct_change <= -thresholds["row_count_drop_fail_pct"]:
        outcome = "FAIL"
        reasons.append(f"row count dropped {pct_change}% vs baseline")

    if outcome != "FAIL":
        if drift["dtype_changes"] and thresholds["type_change_action"] == "warn":
            outcome = "WARN"
            reasons.append(f"dtype changes: {list(drift['dtype_changes'])}")

        spiking = {col: d for col, d in drift["null_pct_deltas"].items()
                   if d >= thresholds["null_pct_spike_warn"]}
        if spiking:
            outcome = "WARN"
            reasons.append(f"null % spike: {spiking}")

        if drift["new_columns"] and thresholds["new_column_action"] == "log_and_alert":
            reasons.append(f"new columns (logged): {drift['new_columns']}")

    return {"outcome": outcome, "reasons": reasons, "drift": drift}
