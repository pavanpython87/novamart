import pandas as pd

from src.validation.rules_engine import evaluate_source

SHOPIFY_RULES = {
    "shopify": {
        "required_columns": ["order_id", "customer_email", "order_date", "total_amount", "status"],
        "business_rules": [
            {"rule": "total_amount_positive", "column": "total_amount",
             "condition": ">= 0", "on_fail": "quarantine"},
            {"rule": "order_date_not_future", "column": "order_date",
             "condition": "<= today", "on_fail": "quarantine"},
        ],
    },
    "shipping": {
        "required_columns": ["tracking_number", "ship_date"],
        "business_rules": [
            {"rule": "delivery_after_ship", "condition": "delivery_date >= ship_date",
             "on_fail": "warn"},
        ],
    },
}


def test_evaluate_source_detects_missing_columns():
    df = pd.DataFrame({"order_id": ["1"], "total_amount": [10]})
    result = evaluate_source(df, "shopify", SHOPIFY_RULES)
    assert set(result["missing_columns"]) == {"customer_email", "order_date", "status"}


def test_evaluate_source_flags_negative_amounts_for_quarantine():
    df = pd.DataFrame({"total_amount": [10, -5, 20], "order_date": ["2024-01-01"] * 3})
    result = evaluate_source(df, "shopify", SHOPIFY_RULES)
    assert result["quarantine_mask"].tolist() == [False, True, False]


def test_evaluate_source_flags_future_dates():
    df = pd.DataFrame({"total_amount": [10, 10], "order_date": ["2024-01-01", "2099-01-01"]})
    result = evaluate_source(df, "shopify", SHOPIFY_RULES)
    assert result["quarantine_mask"].tolist() == [False, True]


def test_evaluate_source_cross_column_warn_rule():
    df = pd.DataFrame({
        "tracking_number": ["A", "B", "C"],
        "ship_date": ["2024-01-01", "2024-01-05", "2024-01-10"],
        "delivery_date": ["2024-01-03", "2024-01-01", None],  # B: delivered before ship = bad
    })
    result = evaluate_source(df, "shipping", SHOPIFY_RULES)
    assert result["warn_mask"].tolist() == [False, True, False]  # null delivery passes
    assert result["quarantine_mask"].tolist() == [False, False, False]


def test_evaluate_source_skips_rule_when_column_absent():
    df = pd.DataFrame({"order_id": ["1"]})
    result = evaluate_source(df, "shopify", SHOPIFY_RULES)
    skipped_rules = [r["rule"] for r in result["rule_results"] if r["skipped"]]
    assert "total_amount_positive" in skipped_rules
    assert "order_date_not_future" in skipped_rules


def test_evaluate_source_unknown_source_returns_empty_rules():
    df = pd.DataFrame({"a": [1]})
    result = evaluate_source(df, "nonexistent_source", SHOPIFY_RULES)
    assert result["missing_columns"] == []
    assert result["rule_results"] == []
    assert result["quarantine_mask"].tolist() == [False]
