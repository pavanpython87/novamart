import pandas as pd

from src.profiling.profiler import profile_dataframe


def test_profile_dataframe_basic_counts():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    profile = profile_dataframe(df, "test_source")
    assert profile["source"] == "test_source"
    assert profile["row_count"] == 3
    assert profile["column_count"] == 2


def test_profile_dataframe_null_pct():
    df = pd.DataFrame({"a": [1, None, None, 4]})
    profile = profile_dataframe(df, "s")
    assert profile["columns"]["a"]["null_count"] == 2
    assert profile["columns"]["a"]["null_pct"] == 50.0


def test_profile_dataframe_numeric_summary():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]})
    profile = profile_dataframe(df, "s")
    summary = profile["columns"]["a"]["numeric_summary"]
    assert summary["min"] == 1.0
    assert summary["max"] == 4.0
    assert summary["mean"] == 2.5


def test_profile_dataframe_top_values_for_categorical():
    df = pd.DataFrame({"cat": ["a", "a", "a", "b"]})
    profile = profile_dataframe(df, "s")
    top_values = profile["columns"]["cat"]["top_values"]
    assert top_values["a"] == 3
    assert top_values["b"] == 1


def test_profile_dataframe_empty_column_has_no_summary():
    df = pd.DataFrame({"a": [None, None]})
    profile = profile_dataframe(df, "s")
    assert "numeric_summary" not in profile["columns"]["a"]
    assert "top_values" not in profile["columns"]["a"]
    assert profile["columns"]["a"]["null_pct"] == 100.0
