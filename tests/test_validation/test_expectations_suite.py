import pandas as pd

from src.validation.expectations_suite import ExpectationSuite


def test_expectation_suite_validates_against_real_config():
    df = pd.DataFrame({
        "order_id": ["1", "2"],
        "order_date": ["2024-01-01", "2024-01-02"],
        "gross_revenue": [10.0, -5.0],
    })
    suite = ExpectationSuite("orders")
    result = suite.validate(df)
    assert result["source"] == "orders"
    assert result["quarantine_mask"].tolist() == [False, True]


def test_expectation_suite_accepts_custom_rules():
    rules = {"custom": {"required_columns": [], "business_rules": [
        {"rule": "positive", "column": "x", "condition": ">= 0", "on_fail": "quarantine"},
    ]}}
    suite = ExpectationSuite("custom", rules)
    df = pd.DataFrame({"x": [1, -1]})
    result = suite.validate(df)
    assert result["quarantine_mask"].tolist() == [False, True]
