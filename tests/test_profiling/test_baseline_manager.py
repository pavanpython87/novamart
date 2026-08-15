import pandas as pd

from src.profiling.baseline_manager import BaselineManager
from src.profiling.profiler import profile_dataframe


def test_baseline_roundtrip(tmp_path):
    mgr = BaselineManager(tmp_path)
    df = pd.DataFrame({"a": [1, 2, 3]})
    profile = profile_dataframe(df, "shopify")
    assert mgr.load("shopify") is None
    mgr.save("shopify", profile)
    loaded = mgr.load("shopify")
    assert loaded["row_count"] == 3


def test_compute_delta_row_count_change(tmp_path):
    mgr = BaselineManager(tmp_path)
    baseline = profile_dataframe(pd.DataFrame({"a": [1, 2]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1, 2, 3, 4]}), "s")
    delta = mgr.compute_delta(current, baseline)
    assert delta["row_count_delta"] == 2
    assert delta["row_count_pct_change"] == 100.0


def test_compute_delta_detects_new_and_missing_columns(tmp_path):
    mgr = BaselineManager(tmp_path)
    baseline = profile_dataframe(pd.DataFrame({"a": [1], "b": [2]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1], "c": [3]}), "s")
    delta = mgr.compute_delta(current, baseline)
    assert delta["new_columns"] == ["c"]
    assert delta["missing_columns"] == ["b"]


def test_compute_delta_detects_null_pct_and_dtype_changes(tmp_path):
    mgr = BaselineManager(tmp_path)
    baseline = profile_dataframe(pd.DataFrame({"a": [1, 2, 3, 4]}), "s")
    current = profile_dataframe(pd.DataFrame({"a": [1, None, None, None]}), "s")
    delta = mgr.compute_delta(current, baseline)
    assert delta["null_pct_deltas"]["a"] == 75.0
    assert "a" in delta["dtype_changes"]
