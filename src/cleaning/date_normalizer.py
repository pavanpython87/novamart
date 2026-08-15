"""Normalizes dates from many input formats (MM/DD/YYYY, DD-MM-YYYY,
'March 1, 2024', ISO with/without time, Unix epoch seconds, etc.) to
ISO 8601: YYYY-MM-DD for date-only values, or a full ISO timestamp when a
time component was present in the source.
"""

from __future__ import annotations

import datetime as dt
import math

from dateutil import parser as dateutil_parser

_EPOCH_MIN = 10**9   # ~2001-09-09, floor for plausible epoch-seconds values
_EPOCH_MAX = 10**10  # ~2286-11-20, ceiling before this looks like epoch-ms


def _from_epoch_seconds(value: float) -> str:
    return dt.datetime.fromtimestamp(value, tz=dt.UTC).date().isoformat()


def normalize_date(raw, dayfirst: bool = False) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    if isinstance(raw, dt.datetime):
        return raw.isoformat()
    if isinstance(raw, dt.date):
        return raw.isoformat()
    if isinstance(raw, (int, float)) and _EPOCH_MIN <= abs(raw) <= _EPOCH_MAX:
        return _from_epoch_seconds(raw)

    text = str(raw).strip()
    if not text:
        return None
    if text.isdigit() and _EPOCH_MIN <= int(text) <= _EPOCH_MAX:
        return _from_epoch_seconds(int(text))

    try:
        parsed = dateutil_parser.parse(text, dayfirst=dayfirst)
    except (ValueError, OverflowError, dateutil_parser.ParserError):
        return None

    had_time_component = ":" in text or "t" in text.lower()
    return parsed.isoformat() if had_time_component else parsed.date().isoformat()
