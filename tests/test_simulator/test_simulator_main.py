import datetime as dt

from src.simulator.simulator_main import generate_range
from src.simulator.universe import Universe

# Shared universe across tests to avoid rebuilding the 5000-customer pool repeatedly.
UNIVERSE = Universe(seed=1)


def test_generate_range_single_day_writes_all_daily_sources(tmp_path):
    date = dt.date(2024, 1, 7)  # a Sunday -> also triggers weekly customer sync
    summary = generate_range(date, date, tmp_path, seed=1, universe=UNIVERSE)

    assert summary["pos"] == 24  # one file per hour
    assert summary["shopify"] == 4  # every 6 hours: 00, 06, 12, 18
    assert summary["amazon"] == 1
    assert summary["shipping"] == 3  # fedex + ups + usps
    assert summary["customers"] == 1  # Sunday sync

    assert list((tmp_path / "pos").glob("*.json"))
    assert list((tmp_path / "shopify").glob("*.csv"))
    assert list((tmp_path / "amazon").glob("*.xlsx"))
    assert list((tmp_path / "shipping").glob("fedex_*.xml"))
    assert list((tmp_path / "shipping").glob("ups_*.csv"))
    assert list((tmp_path / "shipping").glob("usps_*.txt"))
    assert list((tmp_path / "customers").glob("*.csv"))


def test_generate_range_first_of_month_writes_product_catalog(tmp_path):
    date = dt.date(2024, 2, 1)
    summary = generate_range(date, date, tmp_path, seed=2, universe=UNIVERSE)
    assert summary["products"] == 1
    assert list((tmp_path / "products").glob("*.db"))


def test_generate_range_non_month_start_skips_products(tmp_path):
    date = dt.date(2024, 2, 15)
    summary = generate_range(date, date, tmp_path, seed=3, universe=UNIVERSE)
    assert summary["products"] == 0


def test_generate_range_multi_day_span(tmp_path):
    start = dt.date(2024, 3, 1)
    end = dt.date(2024, 3, 3)
    summary = generate_range(start, end, tmp_path, seed=4, universe=UNIVERSE)
    assert summary["pos"] == 24 * 3
    assert summary["amazon"] == 3
