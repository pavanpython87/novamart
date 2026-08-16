"""Thin Prefect task wrapper around the data simulator, used by flows that
need to generate a day's (or a range's) worth of source data before
ingesting it — e.g. the daily GitHub Actions run against a fresh clone
with no incoming data yet.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from prefect import task

from src.simulator.simulator_main import generate_range


@task(name="simulate-data", retries=2, retry_delay_seconds=5)
def simulate_data(
    start_date: dt.date, end_date: dt.date, output_dir: str | Path = "data/incoming",
    seed: int = 42, chaos_level: float = 1.0,
) -> dict[str, int]:
    """Generates source files for [start_date, end_date] into output_dir.
    Returns a dict of source -> file count written."""
    return generate_range(start_date, end_date, Path(output_dir), seed=seed, chaos_level=chaos_level)
