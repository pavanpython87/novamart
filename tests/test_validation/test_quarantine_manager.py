import pandas as pd

from src.validation.expectations_suite import ExpectationSuite
from src.validation.quarantine_manager import QuarantineManager, route

RULES = {
    "shopify": {
        "required_columns": [],
        "business_rules": [
            {"rule": "total_amount_positive", "column": "total_amount",
             "condition": ">= 0", "on_fail": "quarantine"},
        ],
    },
}


def test_route_splits_clean_and_quarantined_rows():
    df = pd.DataFrame({"order_id": ["1", "2", "3"], "total_amount": [10, -5, 20]})
    result = ExpectationSuite("shopify", RULES).validate(df)
    clean, quarantined = route(df, result)
    assert list(clean["order_id"]) == ["1", "3"]
    assert list(quarantined["order_id"]) == ["2"]
    assert quarantined.iloc[0]["reason_codes"] == "total_amount_positive"


def test_route_with_no_failures_returns_empty_quarantine():
    df = pd.DataFrame({"order_id": ["1"], "total_amount": [10]})
    result = ExpectationSuite("shopify", RULES).validate(df)
    clean, quarantined = route(df, result)
    assert len(clean) == 1
    assert quarantined.empty


def test_quarantine_manager_persists_rows(tmp_path):
    df = pd.DataFrame({"order_id": ["1", "2"], "total_amount": [10, -5]})
    result = ExpectationSuite("shopify", RULES).validate(df)
    _, quarantined = route(df, result)

    mgr = QuarantineManager(tmp_path / "quarantine.db")
    written = mgr.persist("shopify", quarantined, batch_id="batch-1")
    assert written == 1

    import sqlite3
    conn = sqlite3.connect(tmp_path / "quarantine.db")
    rows = conn.execute("SELECT order_id, reason_codes, batch_id FROM quarantine_shopify").fetchall()
    conn.close()
    assert rows == [("2", "total_amount_positive", "batch-1")]


def test_quarantine_manager_persist_empty_returns_zero(tmp_path):
    mgr = QuarantineManager(tmp_path / "quarantine.db")
    written = mgr.persist("shopify", pd.DataFrame(), batch_id="batch-1")
    assert written == 0
