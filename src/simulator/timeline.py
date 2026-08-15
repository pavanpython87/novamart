"""Shared timeline constants for the 2-year historical simulation.

Centralizes the "quality degradation timeline" (project plan section 13.3)
so that individual source simulators and the chaos injector agree on
exactly when schema-drift events happen relative to the historical start
date.
"""

from __future__ import annotations

import datetime as dt

HISTORICAL_START = dt.date(2024, 1, 1)
HISTORICAL_END = dt.date(2025, 12, 31)


def add_months(date: dt.date, n: int) -> dt.date:
    month_index = date.month - 1 + n
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    return date.replace(year=year, month=month, day=1)


def month_index(date: dt.date, start: dt.date = HISTORICAL_START) -> int:
    """0-indexed number of whole months elapsed since `start`."""
    return (date.year - start.year) * 12 + (date.month - start.month)


# -- named schema-drift / quality-timeline events (section 13.3) -------

def shopify_has_discount_type(date: dt.date) -> bool:
    """Month 6+: Shopify export adds a new `discount_type` column."""
    return month_index(date) >= 6


def amazon_fee_column_renamed(date: dt.date) -> bool:
    """Month 9+: Amazon renames `referral_fee` -> `referral_fee_amount`."""
    return month_index(date) >= 9


def pos_v4_active(date: dt.date) -> bool:
    """Month 12+: POS system upgrades from v3 to v4 JSON structure.
    Months 12-13 are a transition period where both formats can appear."""
    return month_index(date) >= 12


def pos_v4_transition(date: dt.date) -> bool:
    idx = month_index(date)
    return 12 <= idx <= 13


def duplicate_upload_window(date: dt.date) -> bool:
    """Month 10-11: elevated chance of duplicate file uploads."""
    return 10 <= month_index(date) <= 11


def increasing_chaos_window(date: dt.date) -> bool:
    """Month 13-18: more corrupted/empty files, higher Q4 return rates."""
    return 13 <= month_index(date) <= 18


def stabilization_window(date: dt.date) -> bool:
    """Month 19-24: quality issues plateau."""
    return month_index(date) >= 19


def quality_degradation_stage(date: dt.date) -> str:
    idx = month_index(date)
    if idx < 6:
        return "baseline"
    if idx == 6:
        return "shopify_schema_drift"
    if idx in (7, 8):
        return "gradual_quality_decline"
    if idx == 9:
        return "amazon_breaking_schema"
    if idx in (10, 11):
        return "duplicate_file_uploads"
    if idx == 12:
        return "pos_system_upgrade"
    if 13 <= idx <= 18:
        return "increasing_chaos"
    return "stabilization"
