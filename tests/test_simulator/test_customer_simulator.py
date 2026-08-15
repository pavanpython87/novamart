import csv
import datetime as dt
import random

from src.simulator.customer_simulator import generate_customer_sync
from src.simulator.universe import Universe

UNIVERSE = Universe(seed=1)


def test_generate_customer_sync_writes_csv(tmp_path):
    path = generate_customer_sync(UNIVERSE, dt.date(2024, 3, 3), tmp_path,
                                   rng=random.Random(1), num_new=50, num_updated=10)
    assert path.exists()
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 60  # at least one row per synced customer (more if cross-channel)
    sync_types = {r["sync_type"] for r in rows}
    assert sync_types == {"new", "updated"}


def test_pos_rows_may_lack_email_amazon_rows_may_lack_phone(tmp_path):
    path = generate_customer_sync(UNIVERSE, dt.date(2024, 3, 3), tmp_path,
                                   rng=random.Random(2), num_new=500, num_updated=0)
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pos_rows = [r for r in rows if r["channel"] == "pos"]
    amazon_rows = [r for r in rows if r["channel"] == "amazon"]
    assert any(r["email"] == "" for r in pos_rows)
    assert any(r["phone"] == "" for r in amazon_rows)


def test_filename_pattern(tmp_path):
    path = generate_customer_sync(UNIVERSE, dt.date(2024, 6, 9), tmp_path,
                                   rng=random.Random(3), num_new=5, num_updated=0)
    assert path.name == "customer_sync_20240609.csv"
