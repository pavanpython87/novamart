from src.ingestion.incremental_tracker import IncrementalTracker


def test_new_file_is_new_or_changed(tmp_path):
    tracker = IncrementalTracker(tmp_path / "state.db")
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    assert tracker.is_new_or_changed("shopify", f) is True


def test_processed_file_is_not_new_or_changed(tmp_path):
    tracker = IncrementalTracker(tmp_path / "state.db")
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    tracker.mark_processed("shopify", f, row_count=1)
    assert tracker.is_new_or_changed("shopify", f) is False


def test_changed_file_content_is_detected(tmp_path):
    tracker = IncrementalTracker(tmp_path / "state.db")
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    tracker.mark_processed("shopify", f, row_count=1)
    f.write_text("a,b\n1,2\n3,4\n")
    assert tracker.is_new_or_changed("shopify", f) is True


def test_hwm_roundtrip(tmp_path):
    tracker = IncrementalTracker(tmp_path / "state.db")
    assert tracker.get_hwm("products", "updated_at") is None
    tracker.set_hwm("products", "updated_at", "2024-03-01T00:00:00")
    assert tracker.get_hwm("products", "updated_at") == "2024-03-01T00:00:00"
    tracker.set_hwm("products", "updated_at", "2024-04-01T00:00:00")
    assert tracker.get_hwm("products", "updated_at") == "2024-04-01T00:00:00"


def test_state_persists_across_tracker_instances(tmp_path):
    db_path = tmp_path / "state.db"
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    IncrementalTracker(db_path).mark_processed("shopify", f)
    tracker2 = IncrementalTracker(db_path)
    assert tracker2.is_new_or_changed("shopify", f) is False
