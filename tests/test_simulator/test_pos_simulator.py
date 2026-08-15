import datetime as dt
import json
import random

from src.simulator.pos_simulator import generate_pos_batch
from src.simulator.universe import Universe

UNIVERSE = Universe(seed=1)


def test_generate_pos_batch_v3_structure(tmp_path):
    batch_dt = dt.datetime(2024, 3, 1, 14, 0)  # before month 12 -> v3
    path = generate_pos_batch(UNIVERSE, batch_dt, num_transactions=15,
                               output_dir=tmp_path, rng=random.Random(1))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["transaction_count"] == 15
    txn = payload["transactions"][0]
    assert "items" in txn
    assert "line_items" not in txn


def test_generate_pos_batch_v4_structure(tmp_path):
    batch_dt = dt.datetime(2025, 3, 1, 14, 0)  # month index 14 -> v4 active
    path = generate_pos_batch(UNIVERSE, batch_dt, num_transactions=15,
                               output_dir=tmp_path, rng=random.Random(2))
    payload = json.loads(path.read_text(encoding="utf-8"))
    txn = payload["transactions"][0]
    assert "line_items" in txn
    assert "items" not in txn


def test_pos_filename_patterns(tmp_path):
    batch_dt = dt.datetime(2024, 5, 15, 9, 30)
    hourly = generate_pos_batch(UNIVERSE, batch_dt, num_transactions=5,
                                 output_dir=tmp_path, rng=random.Random(3))
    daily = generate_pos_batch(UNIVERSE, batch_dt, num_transactions=5,
                                output_dir=tmp_path, rng=random.Random(3), daily=True)
    assert hourly.name == "pos_txn_20240515_0930.json"
    assert daily.name == "pos_transactions_2024_05_15.json"


def test_card_payment_structure_matches_version(tmp_path):
    v3_date = dt.datetime(2024, 3, 1, 14, 0)
    path = generate_pos_batch(UNIVERSE, v3_date, num_transactions=30,
                               output_dir=tmp_path, rng=random.Random(42))
    payload = json.loads(path.read_text(encoding="utf-8"))
    card_txns = [t for t in payload["transactions"] if t["payment"]["method"] == "card"]
    assert card_txns
    for t in card_txns:
        assert "card_type" in t["payment"]
        assert "instrument" not in t["payment"]
