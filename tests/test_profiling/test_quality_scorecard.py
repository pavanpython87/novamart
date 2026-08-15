import pandas as pd

from src.profiling.profiler import profile_dataframe
from src.profiling.quality_scorecard import load_thresholds, score_batch


def test_score_batch_passes_with_no_baseline():
    current = profile_dataframe(pd.DataFrame({"a": [1, 2]}), "s")
    result = score_batch(current, None)
    assert result["outcome"] == "PASS"


def test_score_batch_passes_when_stable():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": ["x", "y", "x", "y"]})
    baseline = profile_dataframe(df, "s")
    current = profile_dataframe(df, "s")
    result = score_batch(current, baseline)
    assert result["outcome"] == "PASS"


def test_score_batch_fails_on_missing_columns():
    baseline = profile_dataframe(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1, 2]}), "s")
    result = score_batch(current, baseline)
    assert result["outcome"] == "FAIL"
    assert any("missing columns" in r for r in result["reasons"])


def test_score_batch_fails_on_row_count_drop():
    baseline = profile_dataframe(pd.DataFrame({"a": list(range(100))}), "s")
    current = profile_dataframe(pd.DataFrame({"a": list(range(10))}), "s")
    result = score_batch(current, baseline)
    assert result["outcome"] == "FAIL"


def test_score_batch_warns_on_null_pct_spike():
    baseline = profile_dataframe(pd.DataFrame({"a": [1, 2, 3, 4]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1, None, None, None]}), "s")
    result = score_batch(current, baseline)
    assert result["outcome"] == "WARN"


def test_score_batch_new_columns_logged_but_not_escalated():
    baseline = profile_dataframe(pd.DataFrame({"a": [1, 2]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), "s")
    result = score_batch(current, baseline)
    assert result["outcome"] == "PASS"
    assert any("new columns" in r for r in result["reasons"])


def test_load_thresholds_reads_pipeline_config():
    thresholds = load_thresholds()
    assert thresholds["null_pct_spike_warn"] == 20
    assert thresholds["row_count_drop_fail_pct"] == 50
