import pandas as pd

from src.profiling.drift_detector import (
    detect_drift,
    numeric_mean_shift,
    population_stability_index,
)
from src.profiling.profiler import profile_dataframe


def test_population_stability_index_identical_distributions_near_zero():
    dist = {"a": 50, "b": 50}
    assert population_stability_index(dist, dist) == 0.0


def test_population_stability_index_detects_shift():
    baseline = {"a": 90, "b": 10}
    current = {"a": 10, "b": 90}
    psi = population_stability_index(current, baseline)
    assert psi > 0.25  # significant shift


def test_numeric_mean_shift_zero_when_identical():
    summary = {"mean": 10.0, "std": 2.0}
    assert numeric_mean_shift(summary, summary) == 0.0


def test_numeric_mean_shift_scales_with_std_distance():
    baseline = {"mean": 10.0, "std": 2.0}
    current = {"mean": 16.0, "std": 2.0}
    assert numeric_mean_shift(current, baseline) == 3.0


def test_numeric_mean_shift_handles_zero_std():
    baseline = {"mean": 10.0, "std": 0.0}
    current = {"mean": 12.0, "std": 0.0}
    assert numeric_mean_shift(current, baseline) == 0.0


def test_detect_drift_combines_schema_and_column_drift():
    baseline = profile_dataframe(pd.DataFrame({"amount": [10.0, 12.0, 11.0, 9.0]}), "s")
    current = profile_dataframe(pd.DataFrame({"amount": [100.0, 102.0, 101.0, 99.0]}), "s")
    drift = detect_drift(current, baseline)
    assert "column_drift" in drift
    assert drift["column_drift"]["amount"]["type"] == "numeric"
    assert drift["column_drift"]["amount"]["drift_level"] == "significant"
    assert drift["row_count_delta"] == 0
