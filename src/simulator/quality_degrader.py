"""Computes chaos-injection rates for a given date, so that data quality
degrades progressively over the 2-year historical timeline instead of
being uniformly random (project plan section 13.3).

`chaos_injector.py` calls into this module to decide *how much* of each
issue to inject; this module never mutates data itself.
"""

from __future__ import annotations

import datetime as dt

from src.simulator import timeline as tl

# Baseline (month 1-5) rates for optional fields going null.
BASELINE_NULL_RATES = {"phone": 0.05, "notes": 0.40, "shipping_address_line_2": 0.30}
# Degraded (month 7+) rates for the same fields — ramps linearly between.
DEGRADED_NULL_RATES = {"phone": 0.12, "notes": 0.55, "shipping_address_line_2": 0.45}

BASELINE_CORRUPTED_FILE_RATE = 0.01
INCREASED_CORRUPTED_FILE_RATE = 0.02  # months 13-18
BASELINE_EMPTY_FILE_RATE = 0.005
INCREASED_EMPTY_FILE_RATE = 0.01

BASELINE_DUPLICATE_FILE_RATE = 0.0
ELEVATED_DUPLICATE_FILE_RATE = 0.02  # months 10-11 (duplicate_upload_window)


def optional_field_null_rate(field: str, date: dt.date) -> float:
    """Null rate for an optional field, ramping from baseline (month <=6)
    to degraded (month >=8), linearly across months 7-8."""
    baseline = BASELINE_NULL_RATES.get(field, 0.0)
    degraded = DEGRADED_NULL_RATES.get(field, baseline)
    idx = tl.month_index(date)
    if idx <= 6:
        return baseline
    if idx >= 8:
        return degraded
    # idx == 7: halfway ramp
    return (baseline + degraded) / 2


def corrupted_file_rate(date: dt.date) -> float:
    if tl.increasing_chaos_window(date):
        return INCREASED_CORRUPTED_FILE_RATE
    return BASELINE_CORRUPTED_FILE_RATE


def empty_file_rate(date: dt.date) -> float:
    if tl.increasing_chaos_window(date):
        return INCREASED_EMPTY_FILE_RATE
    return BASELINE_EMPTY_FILE_RATE


def duplicate_file_rate(date: dt.date) -> float:
    if tl.duplicate_upload_window(date):
        return ELEVATED_DUPLICATE_FILE_RATE
    return BASELINE_DUPLICATE_FILE_RATE


def q4_return_rate_multiplier(date: dt.date) -> float:
    """Higher Q4 return rates during the increasing-chaos window (months 13-18)."""
    if tl.increasing_chaos_window(date) and date.month in (11, 12):
        return 1.5
    return 1.0


def stage_summary(date: dt.date) -> dict:
    """A snapshot of all degradation parameters active on a given date —
    useful for logging/debugging which stage of the timeline is active."""
    return {
        "stage": tl.quality_degradation_stage(date),
        "month_index": tl.month_index(date),
        "null_rates": {f: optional_field_null_rate(f, date) for f in BASELINE_NULL_RATES},
        "corrupted_file_rate": corrupted_file_rate(date),
        "empty_file_rate": empty_file_rate(date),
        "duplicate_file_rate": duplicate_file_rate(date),
    }
