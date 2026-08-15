import pandas as pd

from src.dedup.order_deduplicator import deduplicate_orders, deduplicate_within_time_window


def test_deduplicate_orders_exact_key_match():
    df = pd.DataFrame({"order_id": ["A", "A", "B"], "total": [10, 10, 20]})
    deduped, duplicates = deduplicate_orders(df)
    assert list(deduped["order_id"]) == ["A", "B"]
    assert list(duplicates["order_id"]) == ["A"]


def test_deduplicate_orders_no_duplicates():
    df = pd.DataFrame({"order_id": ["A", "B", "C"]})
    deduped, duplicates = deduplicate_orders(df)
    assert len(deduped) == 3
    assert duplicates.empty


def test_deduplicate_within_time_window_close_together_removed():
    df = pd.DataFrame({
        "order_id": ["A", "A"],
        "timestamp": ["2024-03-01T10:00:00", "2024-03-01T10:15:00"],
    })
    deduped, duplicates = deduplicate_within_time_window(
        df, key_columns=["order_id"], timestamp_column="timestamp", window_minutes=60)
    assert len(deduped) == 1
    assert len(duplicates) == 1


def test_deduplicate_within_time_window_far_apart_kept():
    df = pd.DataFrame({
        "order_id": ["A", "A"],
        "timestamp": ["2024-03-01T10:00:00", "2024-03-05T10:00:00"],
    })
    deduped, duplicates = deduplicate_within_time_window(
        df, key_columns=["order_id"], timestamp_column="timestamp", window_minutes=60)
    assert len(deduped) == 2
    assert duplicates.empty


def test_deduplicate_within_time_window_different_keys_never_duplicates():
    df = pd.DataFrame({
        "order_id": ["A", "B"],
        "timestamp": ["2024-03-01T10:00:00", "2024-03-01T10:01:00"],
    })
    deduped, duplicates = deduplicate_within_time_window(
        df, key_columns=["order_id"], timestamp_column="timestamp", window_minutes=60)
    assert len(deduped) == 2
    assert duplicates.empty
