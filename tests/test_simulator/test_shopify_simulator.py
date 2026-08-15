import csv
import datetime as dt
import random

from src.simulator.shopify_simulator import generate_shopify_batch
from src.simulator.universe import Universe

UNIVERSE = Universe(seed=1)


def test_generate_shopify_batch_writes_csv_with_header(tmp_path):
    batch_dt = dt.datetime(2024, 3, 1, 6, 0)
    path = generate_shopify_batch(UNIVERSE, batch_dt, num_orders=20,
                                   output_dir=tmp_path, rng=random.Random(1))
    assert path.exists()
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= 20  # at least one row per order (some orders have multiple items)
    assert "Discount Type" not in reader.fieldnames  # before month 6, no schema drift


def test_shopify_batch_includes_discount_type_after_schema_drift(tmp_path):
    batch_dt = dt.datetime(2024, 8, 1, 6, 0)  # month index 7, after drift at month 6
    path = generate_shopify_batch(UNIVERSE, batch_dt, num_orders=10,
                                   output_dir=tmp_path, rng=random.Random(2))
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert "Discount Type" in reader.fieldnames


def test_shopify_batch_filename_pattern(tmp_path):
    batch_dt = dt.datetime(2024, 5, 15, 12, 0)
    path = generate_shopify_batch(UNIVERSE, batch_dt, num_orders=5,
                                   output_dir=tmp_path, rng=random.Random(3))
    assert path.name == "shopify_batch_20240515_12.csv"


def test_totals_are_non_negative(tmp_path):
    batch_dt = dt.datetime(2024, 2, 1, 6, 0)
    path = generate_shopify_batch(UNIVERSE, batch_dt, num_orders=30,
                                   output_dir=tmp_path, rng=random.Random(4))
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert float(row["Total"]) >= 0
