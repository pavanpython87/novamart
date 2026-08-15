import datetime as dt

from src.simulator import seasonal_patterns as sp


def test_thanksgiving_is_a_thursday():
    for year in (2024, 2025, 2026):
        assert sp.thanksgiving(year).weekday() == 3


def test_black_friday_is_day_after_thanksgiving():
    for year in (2024, 2025):
        assert sp.black_friday(year) == sp.thanksgiving(year) + dt.timedelta(days=1)


def test_is_black_friday_weekend_true_and_false():
    bf = sp.black_friday(2024)
    assert sp.is_black_friday_weekend(bf) is True
    assert sp.is_black_friday_weekend(dt.date(2024, 12, 25)) is False


def test_prime_day_is_july_amazon_only():
    start, end = sp.prime_day(2025)
    assert start.month == 7
    assert sp.seasonal_event_multiplier(start, channel="amazon") == 2.0
    # Not amazon channel -> falls through to normal month-based multiplier
    assert sp.seasonal_event_multiplier(start, channel="shopify") != 2.0


def test_day_of_week_multiplier_weekend_boost():
    monday = dt.date(2025, 3, 3)
    saturday = dt.date(2025, 3, 8)
    assert sp.day_of_week_multiplier(saturday) > sp.day_of_week_multiplier(monday)


def test_monthly_growth_compounds():
    start = dt.date(2024, 1, 1)
    later = dt.date(2024, 7, 1)  # 6 months later
    mult = sp.monthly_growth_multiplier(later, start)
    assert abs(mult - (1.03 ** 6)) < 1e-9


def test_q4_holiday_multiplier():
    assert sp.seasonal_event_multiplier(dt.date(2025, 11, 15)) == 2.5
    assert sp.seasonal_event_multiplier(dt.date(2025, 12, 5)) == 2.5


def test_january_dip_and_return_spike():
    jan = dt.date(2025, 1, 15)
    assert sp.seasonal_event_multiplier(jan) == 0.8
    assert sp.return_rate_multiplier(jan) == 1.8
    assert sp.return_rate_multiplier(dt.date(2025, 5, 1)) == 1.0


def test_product_category_multiplier_winter_and_summer():
    winter = dt.date(2025, 12, 20)
    summer = dt.date(2025, 7, 4)
    assert sp.product_category_multiplier(winter, "Voltix Space Heater", "Seasonal") == 2.0
    assert sp.product_category_multiplier(summer, "Voltix Tower Fan", "Seasonal") == 2.0
    assert sp.product_category_multiplier(summer, "Voltix Space Heater", "Seasonal") == 1.0


def test_volume_multiplier_combines_factors():
    start = dt.date(2024, 1, 1)
    date = dt.date(2024, 1, 1)
    mult = sp.volume_multiplier(date, start, channel="shopify")
    assert mult > 0
