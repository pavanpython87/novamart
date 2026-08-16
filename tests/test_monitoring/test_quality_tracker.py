from src.monitoring.quality_tracker import QualityTracker


def test_record_and_trend(tmp_path):
    tracker = QualityTracker(tmp_path / "quality_trend.jsonl")
    tracker.record("b1", "shopify", "WARN", ["null spike"], {"row_count": 100})
    tracker.record("b1", "amazon", "PASS")
    tracker.record("b2", "shopify", "PASS")

    assert len(tracker.load_all()) == 3
    assert len(tracker.trend("shopify")) == 2
    assert tracker.trend("amazon")[0]["outcome"] == "PASS"


def test_record_scorecard_extracts_outcome_and_metrics(tmp_path):
    tracker = QualityTracker(tmp_path / "quality_trend.jsonl")
    tracker.record_scorecard(
        "b1",
        "pos",
        {"outcome": "FAIL", "reasons": ["missing columns"]},
        profile={"row_count": 250, "column_count": 8},
    )

    record = tracker.trend("pos")[0]
    assert record["outcome"] == "FAIL"
    assert record["reasons"] == ["missing columns"]
    assert record["metrics"] == {"row_count": 250, "column_count": 8}
