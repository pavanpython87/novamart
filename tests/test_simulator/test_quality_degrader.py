import datetime as dt

from src.simulator import quality_degrader as qd


def test_null_rate_baseline_before_month_7():
    date = dt.date(2024, 5, 1)  # month index 4
    assert qd.optional_field_null_rate("phone", date) == qd.BASELINE_NULL_RATES["phone"]


def test_null_rate_degraded_after_month_8():
    date = dt.date(2024, 9, 1)  # month index 8
    assert qd.optional_field_null_rate("phone", date) == qd.DEGRADED_NULL_RATES["phone"]


def test_null_rate_ramps_at_month_7():
    date = dt.date(2024, 8, 1)  # month index 7
    rate = qd.optional_field_null_rate("phone", date)
    assert qd.BASELINE_NULL_RATES["phone"] < rate < qd.DEGRADED_NULL_RATES["phone"]


def test_corrupted_and_empty_file_rate_increase_in_chaos_window():
    normal = dt.date(2024, 3, 1)
    chaos = dt.date(2025, 2, 1)  # month index 13
    assert qd.corrupted_file_rate(chaos) > qd.corrupted_file_rate(normal)
    assert qd.empty_file_rate(chaos) > qd.empty_file_rate(normal)


def test_duplicate_file_rate_elevated_in_window():
    normal = dt.date(2024, 3, 1)
    window = dt.date(2024, 11, 15)  # month index 10
    assert qd.duplicate_file_rate(window) > qd.duplicate_file_rate(normal)


def test_stage_summary_has_expected_keys():
    summary = qd.stage_summary(dt.date(2024, 1, 1))
    assert summary["stage"] == "baseline"
    assert "null_rates" in summary
    assert "corrupted_file_rate" in summary
