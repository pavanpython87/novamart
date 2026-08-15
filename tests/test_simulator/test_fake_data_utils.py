import random
import re

from src.simulator import fake_data_utils as fdu


def test_random_person_name_returns_triple():
    rng = random.Random(42)
    first, last, locale = fdu.random_person_name(rng)
    assert first and last
    assert locale in fdu._LOCALE_WEIGHTS


def test_random_email_is_ascii_and_valid_shape():
    rng = random.Random(1)
    email = fdu.random_email("José", "Müller", rng)
    assert "@" in email
    assert email == email.encode("ascii", "ignore").decode()


def test_random_phone_formats_are_varied():
    rng = random.Random(7)
    formats = {fdu.random_phone(rng) for _ in range(50)}
    assert len(formats) > 5  # should hit multiple format variants


def test_random_phone_specific_format():
    rng = random.Random(0)
    phone = fdu.random_phone(rng, fmt="{a}-{e}-{l}")
    assert re.match(r"^\d{3}-\d{3}-\d{4}$", phone)


def test_random_address_us_and_ca():
    rng = random.Random(3)
    us = fdu.random_address("US", rng)
    ca = fdu.random_address("CA", rng)
    assert us["region"] in fdu.US_STATES
    assert ca["region"] in fdu.CA_PROVINCES
    assert us["country"] == "US"
    assert ca["country"] == "CA"


def test_random_product_name():
    rng = random.Random(5)
    category, name = fdu.random_product_name(rng=rng)
    assert category in fdu.PRODUCT_CATEGORIES
    assert name.split()[0] in fdu.BRANDS


def test_sku_generators_unique_enough():
    rng = random.Random(9)
    skus = {fdu.generate_shopify_sku(rng) for _ in range(20)}
    asins = {fdu.generate_amazon_asin(rng) for _ in range(20)}
    pos_skus = {fdu.generate_pos_internal_sku(rng) for _ in range(20)}
    assert len(skus) > 15
    assert all(a.startswith("B0") and len(a) == 10 for a in asins)
    assert all(s.startswith("POS-") for s in pos_skus)


def test_tracking_number_formats():
    rng = random.Random(11)
    assert fdu.generate_ups_tracking(rng).startswith("1Z")
    assert len(fdu.generate_fedex_tracking(rng)) == 12
    assert fdu.generate_usps_tracking(rng).startswith("9400")
