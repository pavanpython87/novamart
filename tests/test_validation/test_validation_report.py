import pandas as pd

from src.validation.expectations_suite import ExpectationSuite
from src.validation.validation_report import build_report

RULES = {
    "shopify": {
        "required_columns": ["order_id", "missing_col"],
        "business_rules": [
            {"rule": "total_amount_positive", "column": "total_amount",
             "condition": ">= 0", "on_fail": "quarantine"},
        ],
    },
}


def test_build_report_summarizes_validation_result():
    df = pd.DataFrame({"order_id": ["1", "2", "3"], "total_amount": [10, -5, -1]})
    result = ExpectationSuite("shopify", RULES).validate(df)
    report = build_report(result, row_count=len(df))
    assert report["source"] == "shopify"
    assert report["row_count"] == 3
    assert report["missing_columns"] == ["missing_col"]
    assert report["quarantined_count"] == 2
    assert report["rule_breakdown"][0]["fail_count"] == 2
