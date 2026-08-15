import datetime as dt

from src.simulator import timeline as tl


def test_add_months_wraps_year():
    assert tl.add_months(dt.date(2024, 11, 15), 3) == dt.date(2025, 2, 1)


def test_month_index_zero_at_start():
    assert tl.month_index(tl.HISTORICAL_START) == 0
    assert tl.month_index(dt.date(2024, 7, 1)) == 6


def test_shopify_discount_type_timeline():
    assert tl.shopify_has_discount_type(dt.date(2024, 6, 30)) is False
    assert tl.shopify_has_discount_type(dt.date(2024, 7, 1)) is True


def test_amazon_fee_rename_timeline():
    assert tl.amazon_fee_column_renamed(dt.date(2024, 9, 30)) is False
    assert tl.amazon_fee_column_renamed(dt.date(2024, 10, 1)) is True


def test_pos_v4_timeline_and_transition():
    assert tl.pos_v4_active(dt.date(2024, 12, 31)) is False
    assert tl.pos_v4_active(dt.date(2025, 1, 1)) is True
    assert tl.pos_v4_transition(dt.date(2025, 1, 1)) is True
    assert tl.pos_v4_transition(dt.date(2025, 3, 1)) is False


def test_quality_degradation_stage_progression():
    assert tl.quality_degradation_stage(dt.date(2024, 1, 1)) == "baseline"
    assert tl.quality_degradation_stage(dt.date(2024, 7, 1)) == "shopify_schema_drift"
    assert tl.quality_degradation_stage(dt.date(2025, 10, 1)) == "stabilization"
