import pandas as pd
import pytest

from src.transform.time_series_builder import build_all_rollups, build_time_series

ORDERS = pd.DataFrame([
    {"order_date": "2024-01-01", "net_revenue": 100.0},
    {"order_date": "2024-01-02", "net_revenue": 50.0},
    {"order_date": "2024-02-01", "net_revenue": 200.0},
])


def test_build_time_series_daily():
    result = build_time_series(ORDERS, "daily")
    assert len(result) == 32  # Jan 1 through Feb 1 inclusive
    jan1 = result[result["period"] == pd.Timestamp("2024-01-01")]
    assert jan1["net_revenue"].iloc[0] == 100.0


def test_build_time_series_monthly():
    result = build_time_series(ORDERS, "monthly")
    assert len(result) == 2
    assert result["net_revenue"].iloc[0] == 150.0
    assert result["order_count"].iloc[0] == 2


def test_build_time_series_invalid_granularity_raises():
    with pytest.raises(ValueError):
        build_time_series(ORDERS, "yearly")


def test_build_time_series_empty():
    result = build_time_series(pd.DataFrame(columns=["order_date", "net_revenue"]), "daily")
    assert result.empty


def test_build_all_rollups_returns_all_granularities():
    result = build_all_rollups(ORDERS)
    assert set(result.keys()) == {"daily", "weekly", "monthly", "quarterly"}
