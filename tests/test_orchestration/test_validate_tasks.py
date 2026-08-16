import pandas as pd

from src.orchestration.tasks.validate_tasks import validate_and_quarantine
from src.validation.quarantine_manager import QuarantineManager


def test_validate_and_quarantine_splits_and_persists(tmp_path):
    df = pd.DataFrame({
        "order_id": ["1", "2", "3"],
        "order_date": ["2024-01-01", "2024-01-01", "2024-01-01"],
        "gross_revenue": [10, -5, 20],
    })
    mgr = QuarantineManager(tmp_path / "quarantine.db")

    result = validate_and_quarantine.fn(df, "orders", mgr, batch_id="batch-1")
    assert list(result["clean_df"]["order_id"]) == ["1", "3"]
    assert list(result["quarantined_df"]["order_id"]) == ["2"]


def test_validate_and_quarantine_no_failures_skips_persist(tmp_path):
    df = pd.DataFrame({
        "order_id": ["1"],
        "order_date": ["2024-01-01"],
        "gross_revenue": [10],
    })
    mgr = QuarantineManager(tmp_path / "quarantine.db")

    result = validate_and_quarantine.fn(df, "orders", mgr, batch_id="batch-1")
    assert result["quarantined_df"].empty
