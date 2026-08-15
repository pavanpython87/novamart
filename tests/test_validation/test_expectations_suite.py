import pandas as pd

from src.validation.expectations_suite import ExpectationSuite


def test_expectation_suite_validates_against_real_config():
    df = pd.DataFrame({
        "order_id": ["1", "2"],
        "customer_email": ["a@x.com", "b@x.com"],
        "order_date": ["2024-01-01", "2024-01-02"],
        "total_amount": [10.0, -5.0],
        "status": ["paid", "paid"],
    })
    suite = ExpectationSuite("shopify")
    result = suite.validate(df)
    assert result["source"] == "shopify"
    assert result["quarantine_mask"].tolist() == [False, True]


def test_expectation_suite_accepts_custom_rules():
    rules = {"custom": {"required_columns": [], "business_rules": [
        {"rule": "positive", "column": "x", "condition": ">= 0", "on_fail": "quarantine"},
    ]}}
    suite = ExpectationSuite("custom", rules)
    df = pd.DataFrame({"x": [1, -1]})
    result = suite.validate(df)
    assert result["quarantine_mask"].tolist() == [False, True]
