import datetime as dt
import random

import pandas as pd

from src.simulator.amazon_simulator import generate_amazon_batch
from src.simulator.universe import Universe

UNIVERSE = Universe(seed=1)


def test_generate_amazon_batch_creates_four_sheets(tmp_path):
    order_date = dt.date(2024, 3, 1)
    path = generate_amazon_batch(UNIVERSE, order_date, num_orders=25,
                                  output_dir=tmp_path, rng=random.Random(1))
    assert path.exists()
    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets.keys()) == {"Orders", "Returns", "Fee Breakdown", "Adjustments"}
    assert len(sheets["Orders"]) == 25


def test_amazon_batch_uses_referral_fee_before_rename(tmp_path):
    order_date = dt.date(2024, 3, 1)  # month index 2, before rename at month 9
    path = generate_amazon_batch(UNIVERSE, order_date, num_orders=10,
                                  output_dir=tmp_path, rng=random.Random(2))
    orders_df = pd.read_excel(path, sheet_name="Orders")
    assert "referral_fee" in orders_df.columns
    assert "referral_fee_amount" not in orders_df.columns


def test_amazon_batch_uses_renamed_fee_column_after_month_9(tmp_path):
    order_date = dt.date(2024, 11, 1)  # month index 10, after rename
    path = generate_amazon_batch(UNIVERSE, order_date, num_orders=10,
                                  output_dir=tmp_path, rng=random.Random(3))
    orders_df = pd.read_excel(path, sheet_name="Orders")
    assert "referral_fee_amount" in orders_df.columns
    assert "referral_fee" not in orders_df.columns


def test_amazon_filename_pattern(tmp_path):
    order_date = dt.date(2024, 6, 15)
    path = generate_amazon_batch(UNIVERSE, order_date, num_orders=5,
                                  output_dir=tmp_path, rng=random.Random(4))
    assert path.name == "amazon_daily_20240615.xlsx"


def test_returns_only_reference_shipped_orders(tmp_path):
    order_date = dt.date(2024, 4, 1)
    path = generate_amazon_batch(UNIVERSE, order_date, num_orders=200,
                                  output_dir=tmp_path, rng=random.Random(5))
    orders_df = pd.read_excel(path, sheet_name="Orders")
    returns_df = pd.read_excel(path, sheet_name="Returns")
    shipped_ids = set(orders_df.loc[orders_df["order-status"] == "Shipped", "amazon-order-id"])
    assert set(returns_df["amazon-order-id"]).issubset(shipped_ids)
