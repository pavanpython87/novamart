"""Orchestrates all source-specific generators on their respective
schedules (project plan section 3.1) and layers file-level chaos on top
using quality_degrader-driven rates.

Volume base ranges are taken from the "ongoing" per-batch counts in
section 3.1 (e.g. Shopify 100-200 orders every 6 hours) rather than the
smaller "seasonal_patterns" base-daily-volume figures, since the former is
what the historical-data target of 1M+ records is built from.

NOTE: row-level chaos (currency symbols, mixed case, encoding issues,
etc.) is available in chaos_injector.py but is applied selectively here
via a small representative set of hooks per source, not exhaustively for
every issue type — extending coverage is a matter of calling more
chaos_injector functions in each `_generate_*` function below.
"""

from __future__ import annotations

import datetime as dt
import logging
import random
from pathlib import Path

from src.simulator import chaos_injector as ci
from src.simulator import quality_degrader as qd
from src.simulator import seasonal_patterns as sp
from src.simulator import shipping_simulator as ship_sim
from src.simulator.amazon_simulator import generate_amazon_batch
from src.simulator.customer_simulator import generate_customer_sync
from src.simulator.pos_simulator import generate_pos_batch
from src.simulator.product_simulator import generate_product_catalog
from src.simulator.shopify_simulator import generate_shopify_batch
from src.simulator.timeline import HISTORICAL_START
from src.simulator.universe import Universe

logger = logging.getLogger(__name__)

BASE_RANGES = {
    "pos_hourly": (20, 35),
    "shopify_6h": (100, 200),
    "amazon_daily": (400, 600),
    "shipping_daily_total": 250,
    "customers_weekly_new": (200, 400),
    "customers_weekly_updated": 50,
    "products_monthly": None,  # full catalog snapshot every month
}

SHIPPING_CARRIER_SPLIT = {"fedex": 0.40, "ups": 0.35, "usps": 0.25}


def _scaled_count(base_range: tuple[int, int], date: dt.date, channel: str | None,
                   rng: random.Random) -> int:
    lo, hi = base_range
    base = rng.randint(lo, hi)
    mult = sp.volume_multiplier(date, HISTORICAL_START, channel)
    return max(1, round(base * mult))


def _apply_file_chaos(filepath: Path, date: dt.date, rng: random.Random,
                       chaos_level: float) -> list[Path]:
    """Rolls for duplicate-upload / corrupted / empty file outcomes for a
    just-written file. Returns any extra file paths created (duplicates)."""
    extra_paths: list[Path] = []
    roll = rng.random()
    dup_rate = qd.duplicate_file_rate(date) * chaos_level
    corrupt_rate = qd.corrupted_file_rate(date) * chaos_level
    empty_rate = qd.empty_file_rate(date) * chaos_level

    if roll < empty_rate:
        ci.empty_file(filepath)
        logger.info("chaos: emptied %s", filepath.name)
    elif roll < empty_rate + corrupt_rate:
        ci.truncate_file(filepath)
        logger.info("chaos: truncated %s", filepath.name)
    elif roll < empty_rate + corrupt_rate + dup_rate:
        extra_paths.append(ci.duplicate_file(filepath, rng))
        logger.info("chaos: duplicated %s", filepath.name)

    return extra_paths


# -- per-cadence generation steps -----------------------------------------

def generate_pos_hour(universe: Universe, batch_dt: dt.datetime, output_dir: Path,
                       rng: random.Random, chaos_level: float = 1.0) -> list[Path]:
    count = _scaled_count(BASE_RANGES["pos_hourly"], batch_dt.date(), "pos", rng)
    path = generate_pos_batch(universe, batch_dt, count, output_dir / "pos", rng)
    return [path, *_apply_file_chaos(path, batch_dt.date(), rng, chaos_level)]


def generate_shopify_period(universe: Universe, batch_dt: dt.datetime, output_dir: Path,
                             rng: random.Random, start_order_number: int,
                             chaos_level: float = 1.0) -> list[Path]:
    count = _scaled_count(BASE_RANGES["shopify_6h"], batch_dt.date(), "shopify", rng)
    path = generate_shopify_batch(universe, batch_dt, count, output_dir / "shopify", rng,
                                   start_order_number=start_order_number)
    return [path, *_apply_file_chaos(path, batch_dt.date(), rng, chaos_level)]


def generate_amazon_day(universe: Universe, date: dt.date, output_dir: Path,
                         rng: random.Random, chaos_level: float = 1.0) -> list[Path]:
    count = _scaled_count(BASE_RANGES["amazon_daily"], date, "amazon", rng)
    path = generate_amazon_batch(universe, date, count, output_dir / "amazon", rng)
    return [path, *_apply_file_chaos(path, date, rng, chaos_level)]


def generate_shipping_day(date: dt.date, output_dir: Path, rng: random.Random,
                           chaos_level: float = 1.0) -> list[Path]:
    total = round(BASE_RANGES["shipping_daily_total"] * sp.volume_multiplier(date, HISTORICAL_START))
    paths = []
    for carrier, share in SHIPPING_CARRIER_SPLIT.items():
        count = max(1, round(total * share))
        path = ship_sim.generate_shipping_batch(carrier, date, count, output_dir / "shipping", rng)
        paths.append(path)
        paths.extend(_apply_file_chaos(path, date, rng, chaos_level))
    return paths


def generate_customers_week(universe: Universe, date: dt.date, output_dir: Path,
                             rng: random.Random, chaos_level: float = 1.0) -> list[Path]:
    lo, hi = BASE_RANGES["customers_weekly_new"]
    num_new = rng.randint(lo, hi)
    path = generate_customer_sync(universe, date, output_dir / "customers", rng,
                                   num_new=num_new,
                                   num_updated=BASE_RANGES["customers_weekly_updated"])
    return [path, *_apply_file_chaos(path, date, rng, chaos_level)]


def generate_products_month(universe: Universe, date: dt.date, output_dir: Path,
                             rng: random.Random, chaos_level: float = 1.0) -> list[Path]:
    path = generate_product_catalog(universe, date, output_dir / "products", rng)
    return [path, *_apply_file_chaos(path, date, rng, chaos_level)]


# -- top-level driver -------------------------------------------------

def generate_range(start_date: dt.date, end_date: dt.date, output_dir: Path,
                    seed: int = 42, chaos_level: float = 1.0,
                    universe: Universe | None = None) -> dict[str, int]:
    """Walks hour-by-hour from start_date 00:00 to end_date 23:00, invoking
    each source generator at its natural cadence. Returns a summary dict of
    files written per source."""
    universe = universe or Universe(seed=seed)
    rng = random.Random(seed)
    output_dir = Path(output_dir)

    summary = {"pos": 0, "shopify": 0, "amazon": 0, "shipping": 0,
               "customers": 0, "products": 0}
    shopify_order_number = 100000
    seen_months: set[tuple[int, int]] = set()

    current = dt.datetime.combine(start_date, dt.time.min)
    end = dt.datetime.combine(end_date, dt.time.min) + dt.timedelta(days=1)

    while current < end:
        date = current.date()

        # Hourly: POS
        summary["pos"] += len(generate_pos_hour(universe, current, output_dir, rng, chaos_level))

        # Every 6 hours: Shopify
        if current.hour % 6 == 0:
            paths = generate_shopify_period(universe, current, output_dir, rng,
                                             shopify_order_number, chaos_level)
            summary["shopify"] += len(paths)
            shopify_order_number += 250  # headroom so numbers never collide across batches

        # Daily at midnight: Amazon + shipping carriers
        if current.hour == 0:
            summary["amazon"] += len(generate_amazon_day(universe, date, output_dir, rng, chaos_level))
            summary["shipping"] += len(generate_shipping_day(date, output_dir, rng, chaos_level))

            # Weekly on Sunday: customer sync
            if date.weekday() == 6:
                summary["customers"] += len(
                    generate_customers_week(universe, date, output_dir, rng, chaos_level))

            # Monthly on the 1st: product catalog
            month_key = (date.year, date.month)
            if date.day == 1 and month_key not in seen_months:
                seen_months.add(month_key)
                summary["products"] += len(
                    generate_products_month(universe, date, output_dir, rng, chaos_level))

        current += dt.timedelta(hours=1)

    return summary
