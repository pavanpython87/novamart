import pytest

from src.dedup.merge_strategy import build_golden_record


def test_build_golden_record_prefers_non_null():
    records = [
        {"email": None, "phone": "+14155550132", "updated_at": "2024-01-01"},
        {"email": "bob@x.com", "phone": None, "updated_at": "2024-01-02"},
    ]
    golden = build_golden_record(records)
    assert golden["email"] == "bob@x.com"
    assert golden["phone"] == "+14155550132"


def test_build_golden_record_most_recent_wins_ties():
    records = [
        {"name": "Bob", "updated_at": "2024-01-01"},
        {"name": "Robert", "updated_at": "2024-06-01"},
    ]
    golden = build_golden_record(records)
    assert golden["name"] == "Robert"


def test_build_golden_record_empty_raises():
    with pytest.raises(ValueError):
        build_golden_record([])


def test_build_golden_record_missing_timestamp_treated_as_oldest():
    records = [
        {"name": "Bob", "updated_at": None},
        {"name": "Robert", "updated_at": "2024-06-01"},
    ]
    golden = build_golden_record(records)
    assert golden["name"] == "Robert"
