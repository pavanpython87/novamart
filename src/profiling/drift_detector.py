"""Schema and statistical drift detection.

Schema drift (new/missing columns, dtype changes, row-count deltas) is
delegated to BaselineManager.compute_delta. This module adds statistical
distribution drift on top of it:
  - categorical columns: Population Stability Index (PSI) over the top-N
    value frequencies captured by profiler.py
  - numeric columns: mean shift expressed in baseline standard deviations

Both are approximations built from the summary statistics profiler.py
already stores (top value counts / mean+std), not full histograms — a
deliberate simplification to avoid persisting raw distributions per batch.
"""

from __future__ import annotations

import math

from src.profiling.baseline_manager import BaselineManager

PSI_EPSILON = 1e-4


def population_stability_index(current_counts: dict[str, int], baseline_counts: dict[str, int]) -> float:
    """PSI over two categorical frequency distributions. Categories present
    in only one distribution are smoothed with a small epsilon so the log
    ratio stays finite."""
    categories = set(current_counts) | set(baseline_counts)
    current_total = sum(current_counts.values()) or 1
    baseline_total = sum(baseline_counts.values()) or 1

    psi = 0.0
    for cat in categories:
        cur_pct = current_counts.get(cat, 0) / current_total or PSI_EPSILON
        base_pct = baseline_counts.get(cat, 0) / baseline_total or PSI_EPSILON
        psi += (cur_pct - base_pct) * math.log(cur_pct / base_pct)
    return round(psi, 4)


def numeric_mean_shift(current_summary: dict, baseline_summary: dict) -> float:
    """Absolute shift in the column mean, expressed in baseline standard
    deviations. Returns 0.0 when the baseline has no spread to compare against."""
    baseline_std = baseline_summary.get("std", 0.0)
    if baseline_std == 0:
        return 0.0
    return round(abs(current_summary["mean"] - baseline_summary["mean"]) / baseline_std, 4)


def _drift_level(score: float, moderate_threshold: float, significant_threshold: float) -> str:
    if score >= significant_threshold:
        return "significant"
    if score >= moderate_threshold:
        return "moderate"
    return "none"


def detect_drift(current: dict, baseline: dict) -> dict:
    schema_delta = BaselineManager().compute_delta(current, baseline)

    column_drift = {}
    for col in set(current["columns"]) & set(baseline["columns"]):
        cur_col = current["columns"][col]
        base_col = baseline["columns"][col]
        if "numeric_summary" in cur_col and "numeric_summary" in base_col:
            score = numeric_mean_shift(cur_col["numeric_summary"], base_col["numeric_summary"])
            column_drift[col] = {
                "type": "numeric",
                "mean_shift_std": score,
                "drift_level": _drift_level(score, moderate_threshold=1.0, significant_threshold=3.0),
            }
        elif "top_values" in cur_col and "top_values" in base_col:
            score = population_stability_index(cur_col["top_values"], base_col["top_values"])
            column_drift[col] = {
                "type": "categorical",
                "psi": score,
                "drift_level": _drift_level(score, moderate_threshold=0.1, significant_threshold=0.25),
            }

    return {**schema_delta, "column_drift": column_drift}
