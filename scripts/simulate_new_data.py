#!/usr/bin/env python
"""Generate the next slice of ongoing data (called daily by GitHub Actions,
or manually for backfill/testing).

Usage:
    python scripts/simulate_new_data.py --date yesterday
    python scripts/simulate_new_data.py --date 2026-01-15
    python scripts/simulate_new_data.py --start-date 2025-06-01 --end-date 2025-06-30
    python scripts/simulate_new_data.py --date yesterday --chaos-level 0.8
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.simulator_main import generate_range  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def _parse_date(value: str) -> dt.date:
    if value == "yesterday":
        return dt.date.today() - dt.timedelta(days=1)
    if value == "today":
        return dt.date.today()
    return dt.date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=_parse_date, help="Single day to generate (or 'yesterday')")
    parser.add_argument("--start-date", type=_parse_date, help="Start of a date range")
    parser.add_argument("--end-date", type=_parse_date, help="End of a date range (inclusive)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/incoming"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chaos-level", type=float, default=1.0,
                         help="Multiplier applied to all chaos-injection rates")
    parser.add_argument("--issues", type=str, default=None,
                         help="Comma-separated issue categories to restrict to "
                              "(currently informational; full per-category filtering "
                              "is a chaos_injector.py extension point)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.date:
        start_date = end_date = args.date
    elif args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
    else:
        start_date = end_date = dt.date.today() - dt.timedelta(days=1)

    logger.info("Simulating new data from %s to %s (chaos_level=%s)",
                start_date, end_date, args.chaos_level)
    summary = generate_range(start_date, end_date, args.output_dir,
                              seed=args.seed, chaos_level=args.chaos_level)
    total = sum(summary.values())
    logger.info("Done. Files written per source: %s (total %d)", summary, total)


if __name__ == "__main__":
    main()
