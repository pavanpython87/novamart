import datetime as dt

import pandas as pd

from src.profiling.profiler import profile_dataframe
from src.profiling.quality_scorecard import score_batch
from src.profiling.report_generator import generate_report


def test_generate_report_writes_json_and_html(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3]})
    profile = profile_dataframe(df, "shopify")
    scorecard = score_batch(profile, None)

    paths = generate_report("shopify", profile, scorecard, output_dir=tmp_path,
                             timestamp=dt.datetime(2024, 3, 1, 10, 0, tzinfo=dt.UTC))
    assert paths["json"].exists()
    assert paths["html"].exists()


def test_generate_report_json_contains_scorecard_outcome(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3]})
    profile = profile_dataframe(df, "shopify")
    scorecard = score_batch(profile, None)
    paths = generate_report("shopify", profile, scorecard, output_dir=tmp_path)
    content = paths["json"].read_text(encoding="utf-8")
    assert '"outcome": "PASS"' in content


def test_generate_report_html_contains_outcome_and_source_name(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3]})
    profile = profile_dataframe(df, "shopify")
    scorecard = score_batch(profile, None)
    paths = generate_report("shopify", profile, scorecard, output_dir=tmp_path)
    html = paths["html"].read_text(encoding="utf-8")
    assert "shopify" in html
    assert "PASS" in html
