import pandas as pd

from src.orchestration.tasks.clean_tasks import clean_source


def test_clean_source_applies_mapped_normalizers():
    df = pd.DataFrame({"phone": ["(415) 555-0132"], "amount": ["$1,234.56"]})
    result = clean_source.fn(df, {"phone": "phone", "amount": "currency"})
    assert result["phone"].iloc[0] == "+14155550132"
    assert result["amount"].iloc[0] == 1234.56


def test_clean_source_ignores_unknown_columns_and_keys():
    df = pd.DataFrame({"phone": ["(415) 555-0132"], "other": ["x"]})
    result = clean_source.fn(df, {"other": "not_a_cleaner", "missing_col": "phone"})
    assert result["other"].iloc[0] == "x"


def test_clean_source_empty_df_returns_empty():
    df = pd.DataFrame()
    result = clean_source.fn(df, {"phone": "phone"})
    assert result.empty
