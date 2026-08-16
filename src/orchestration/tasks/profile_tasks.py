"""Profiling + baseline-comparison task: computes a fresh profile for a
source's batch, compares it against the persisted baseline, and scores
the batch PASS/WARN/FAIL against the configured quality gate thresholds.
"""

from __future__ import annotations

import pandas as pd
from prefect import task

from src.profiling.baseline_manager import BaselineManager
from src.profiling.profiler import profile_dataframe
from src.profiling.quality_scorecard import score_batch


@task(name="profile-and-score")
def profile_and_score(df: pd.DataFrame, source_name: str, baseline_manager: BaselineManager,
                       thresholds: dict | None = None) -> dict:
    """Returns {"profile", "scorecard"} and updates the persisted baseline
    to this batch's profile for next run's comparison."""
    profile = profile_dataframe(df, source_name)
    baseline = baseline_manager.load(source_name)
    scorecard = score_batch(profile, baseline, thresholds)
    baseline_manager.save(source_name, profile)
    return {"profile": profile, "scorecard": scorecard}
