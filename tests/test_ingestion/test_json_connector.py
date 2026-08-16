import datetime as dt
import json
import random

from src.ingestion.json_connector import JSONConnector
from src.simulator.pos_simulator import generate_pos_batch
from src.simulator.universe import Universe


def test_json_connector_flattens_v3_items(tmp_path):
    universe = Universe(seed=1)
    # 2024-03-01 is before the month-12 v3->v4 transition
    path = generate_pos_batch(universe, dt.datetime(2024, 3, 1, 10, 0), 10, tmp_path,
                               rng=random.Random(1))
    conn = JSONConnector(path)
    conn.connect()
    df = conn.extract()
    # One row per line item, so >= one row per transaction.
    assert len(df) >= 10
    assert "item_count" in df.columns
    assert "payment.method" in df.columns
    assert {"sku", "quantity", "line_total"} <= set(df.columns)


def test_json_connector_flattens_v4_line_items(tmp_path):
    universe = Universe(seed=1)
    # 2025-06-01 is well after the month-12 transition -> pure v4
    path = generate_pos_batch(universe, dt.datetime(2025, 6, 1, 10, 0), 10, tmp_path,
                               rng=random.Random(2))
    conn = JSONConnector(path)
    conn.connect()
    df = conn.extract()
    assert len(df) >= 10
    assert "item_count" in df.columns
    assert (df["item_count"] >= 0).all()
    assert {"sku", "quantity", "line_total"} <= set(df.columns)


def test_json_connector_recovers_truncated_json(tmp_path):
    payload = {
        "store_id": "STORE-01",
        "batch_timestamp": "2024-03-01T10:00:00",
        "transaction_count": 2,
        "transactions": [
            {"transaction_id": "TXN-1", "items": [{"sku": "A"}], "payment": {"method": "cash"}},
            {"transaction_id": "TXN-2", "items": [{"sku": "B"}], "payment": {"method": "cash"}},
        ],
    }
    text = json.dumps(payload, indent=2)
    # Simulate a process killed mid-write: cut off partway through the last record.
    cutoff = text.rfind('"transaction_id": "TXN-2"')
    truncated = text[:cutoff] + '"transaction_id": "TXN-2", "ite'
    path = tmp_path / "truncated.json"
    path.write_text(truncated, encoding="utf-8")

    conn = JSONConnector(path)
    conn.connect()
    df = conn.extract()
    assert conn.recovered is True
    assert len(df) == 1
    assert df.iloc[0]["transaction_id"] == "TXN-1"


def test_json_connector_missing_file_raises(tmp_path):
    conn = JSONConnector(tmp_path / "nope.json")
    import pytest
    with pytest.raises(FileNotFoundError):
        conn.connect()
