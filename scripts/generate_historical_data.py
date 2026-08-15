#!/usr/bin/env python
"""Generate the full 2-year historical dataset (~1M+ records) into
data/incoming/. This is a heavy, one-time operation — see docs/data_simulator.md.

Usage:
    python scripts/generate_historical_data.py \
        --start-date 2024-01-01 --end-date 2025-12-31 \
        --output-dir data/incoming/
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.simulator_main import generate_range  # noqa: E402
from src.simulator.timeline import HISTORICAL_END, HISTORICAL_START  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=dt.date.fromisoformat, default=HISTORICAL_START)
    parser.add_argument("--end-date", type=dt.date.fromisoformat, default=HISTORICAL_END)
    parser.add_argument("--output-dir", type=Path, default=Path("data/incoming"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chaos-level", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("Generating historical data from %s to %s into %s",
                args.start_date, args.end_date, args.output_dir)
    summary = generate_range(args.start_date, args.end_date, args.output_dir,
                              seed=args.seed, chaos_level=args.chaos_level)
    total = sum(summary.values())
    logger.info("Done. Files written per source: %s (total %d)", summary, total)


if __name__ == "__main__":
    main()
