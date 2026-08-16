import pandas as pd

from src.orchestration.tasks.profile_tasks import profile_and_score
from src.profiling.baseline_manager import BaselineManager


def test_profile_and_score_returns_profile_and_scorecard(tmp_path):
    mgr = BaselineManager(tmp_path)
    df = pd.DataFrame({"a": [1, 2, 3]})

    result = profile_and_score.fn(df, "shopify", mgr)
    assert result["profile"]["row_count"] == 3
    assert "scorecard" in result


def test_profile_and_score_saves_baseline_for_next_run(tmp_path):
    mgr = BaselineManager(tmp_path)
    df = pd.DataFrame({"a": [1, 2, 3, 4]})

    assert mgr.load("shopify") is None
    profile_and_score.fn(df, "shopify", mgr)
    saved = mgr.load("shopify")
    assert saved["row_count"] == 4
