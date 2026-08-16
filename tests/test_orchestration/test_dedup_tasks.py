import pandas as pd

from src.orchestration.tasks.dedup_tasks import dedup_orders, resolve_customers


def test_resolve_customers_finds_matches():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "email": "bob@x.com"},
        {"record_id": "2", "source": "amazon", "email": "bob@x.com"},
    ])
    matches = resolve_customers.fn(records)
    assert len(matches) == 1
    assert matches[0]["action"] == "auto_merge"


def test_dedup_orders_splits_deduped_and_duplicates():
    df = pd.DataFrame({"order_id": ["A", "A", "B"], "total": [10, 10, 20]})
    result = dedup_orders.fn(df)
    assert list(result["deduped_df"]["order_id"]) == ["A", "B"]
    assert list(result["duplicates_df"]["order_id"]) == ["A"]
