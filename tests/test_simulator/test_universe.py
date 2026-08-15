from src.simulator.universe import (
    NUM_CUSTOMERS,
    NUM_PRODUCTS,
    Universe,
    amazon_fba_fee,
)


def test_universe_builds_expected_counts():
    u = Universe(seed=1)
    assert len(u.products) == NUM_PRODUCTS
    assert len(u.customers) == NUM_CUSTOMERS


def test_products_have_unique_ids_and_valid_category():
    u = Universe(seed=1)
    ids = {p.product_id for p in u.products}
    assert len(ids) == NUM_PRODUCTS
    for p in u.products:
        assert p.amazon_referral_fee_pct >= 0.08
        assert p.unit_cost < p.retail_price


def test_cross_channel_overlap_within_expected_range():
    u = Universe(seed=1)
    overlap = [c for c in u.customers if c.is_cross_channel]
    pct = len(overlap) / len(u.customers)
    assert 0.20 <= pct <= 0.35


def test_customers_for_channel_only_returns_matching():
    u = Universe(seed=1)
    shopify_customers = u.customers_for_channel("shopify")
    assert all("shopify" in c.channels for c in shopify_customers)
    assert all("shopify" in c.identities for c in shopify_customers)


def test_amazon_fba_fee_tiers():
    assert amazon_fba_fee(0.5) == 3.22
    assert amazon_fba_fee(2.5) == 4.75
    assert amazon_fba_fee(100) == 19.99


def test_universe_is_deterministic_with_same_seed():
    u1 = Universe(seed=99)
    u2 = Universe(seed=99)
    assert [p.product_id for p in u1.products] == [p.product_id for p in u2.products]
    assert u1.products[0].name == u2.products[0].name


def test_sample_return_reason_is_valid_code():
    u = Universe(seed=1)
    from src.simulator.universe import RETURN_REASON_CODES
    assert u.sample_return_reason() in RETURN_REASON_CODES
