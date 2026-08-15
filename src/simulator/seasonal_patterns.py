"""Volume multipliers and seasonal calendar logic for the data simulator.

Combines day-of-week effects, month-over-month growth, and named seasonal
events (Q4 holiday, Black Friday/Cyber Monday, Prime Day, back-to-school,
January clearance, summer lull) into a single multiplier that source
simulators apply to their base daily/hourly volumes.
"""

from __future__ import annotations

import datetime as dt

DAY_OF_WEEK_MULTIPLIER = {
    0: 1.0,   # Monday
    1: 1.0,   # Tuesday
    2: 1.0,   # Wednesday
    3: 1.0,   # Thursday
    4: 1.0,   # Friday
    5: 1.3,   # Saturday
    6: 1.1,   # Sunday
}

MONTHLY_GROWTH_RATE = 0.03  # 3% compounding month-over-month

# Product categories that spike seasonally (matches universe.py "Seasonal" items)
WINTER_PRODUCT_KEYWORDS = ("Heater", "Blanket", "Humidifier")
SUMMER_PRODUCT_KEYWORDS = ("Fan", "Dehumidifier")
DECEMBER_GIFT_CATEGORIES = ("Audio", "Gaming", "Wearables", "Accessories")


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> dt.date:
    """weekday: Monday=0 ... Sunday=6. n is 1-indexed occurrence."""
    d = dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    d += dt.timedelta(days=offset + 7 * (n - 1))
    return d


def thanksgiving(year: int) -> dt.date:
    return _nth_weekday_of_month(year, 11, weekday=3, n=4)  # 4th Thursday


def black_friday(year: int) -> dt.date:
    return thanksgiving(year) + dt.timedelta(days=1)


def cyber_monday(year: int) -> dt.date:
    return thanksgiving(year) + dt.timedelta(days=4)


def prime_day(year: int) -> tuple[dt.date, dt.date]:
    """Two-day Prime Day event, second Tuesday-Wednesday of July."""
    start = _nth_weekday_of_month(year, 7, weekday=1, n=2)  # 2nd Tuesday
    return start, start + dt.timedelta(days=1)


def is_black_friday_weekend(date: dt.date) -> bool:
    bf = black_friday(date.year)
    cm = cyber_monday(date.year)
    return bf <= date <= cm


def is_prime_day(date: dt.date) -> bool:
    start, end = prime_day(date.year)
    return start <= date <= end


def day_of_week_multiplier(date: dt.date) -> float:
    return DAY_OF_WEEK_MULTIPLIER[date.weekday()]


def monthly_growth_multiplier(date: dt.date, start_date: dt.date,
                               rate: float = MONTHLY_GROWTH_RATE) -> float:
    months_elapsed = (date.year - start_date.year) * 12 + (date.month - start_date.month)
    return (1 + rate) ** max(months_elapsed, 0)


def seasonal_event_multiplier(date: dt.date, channel: str | None = None) -> float:
    """Named-event / month-window multiplier. `channel` narrows Prime Day
    (Amazon-only) but other events apply across all channels."""
    if is_black_friday_weekend(date):
        return 4.0
    if channel == "amazon" and is_prime_day(date):
        return 2.0
    if date.month in (11, 12):
        return 2.5  # Q4 holiday season
    if date.month == 1:
        return 0.8  # January clearance (order volume dip)
    if date.month in (8, 9):
        return 1.5  # back to school
    if date.month in (6, 7):
        return 0.85  # summer lull
    return 1.0


def return_rate_multiplier(date: dt.date) -> float:
    """Returns spike in January (post-holiday) — applied to return volume,
    not order volume."""
    return 1.8 if date.month == 1 else 1.0


def product_category_multiplier(date: dt.date, product_name: str, category: str) -> float:
    if category == "Seasonal":
        if date.month in (11, 12, 1, 2) and any(k in product_name for k in WINTER_PRODUCT_KEYWORDS):
            return 2.0
        if date.month in (5, 6, 7, 8) and any(k in product_name for k in SUMMER_PRODUCT_KEYWORDS):
            return 2.0
    if date.month == 12 and category in DECEMBER_GIFT_CATEGORIES:
        return 1.4
    return 1.0


def volume_multiplier(date: dt.date, start_date: dt.date, channel: str | None = None) -> float:
    """Overall multiplier combining day-of-week, growth trend, and seasonal events."""
    return (
        day_of_week_multiplier(date)
        * monthly_growth_multiplier(date, start_date)
        * seasonal_event_multiplier(date, channel)
    )
