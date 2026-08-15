"""Reusable fake-data generation primitives shared by all source simulators.

Provides realistic names (including international/Unicode names), US + CA
addresses, phone numbers in multiple formats, product names, and
cross-channel SKU/ASIN identifiers. Everything here is deterministic when
given a seed, so historical data generation is reproducible.
"""

from __future__ import annotations

import random
import string

from faker import Faker

# A mix of locales so ~10-15% of generated names/addresses carry
# international characters (accents, CJK, etc.) as called out in the
# project plan's encoding-problem scenarios.
_LOCALE_WEIGHTS: dict[str, float] = {
    "en_US": 0.70,
    "en_CA": 0.10,
    "es_MX": 0.06,
    "fr_CA": 0.05,
    "de_DE": 0.04,
    "zh_CN": 0.03,
    "ja_JP": 0.02,
}

_fakers: dict[str, Faker] = {locale: Faker(locale) for locale in _LOCALE_WEIGHTS}

PHONE_FORMAT_VARIANTS = [
    "(555) 555-1234",
    "555-555-1234",
    "555.555.1234",
    "5555551234",
    "+1 555 555 1234",
    "1-555-555-1234",
]

PRODUCT_CATEGORIES = {
    "Audio": ["Wireless Earbuds", "Bluetooth Speaker", "Over-Ear Headphones",
              "Soundbar", "Turntable", "Studio Microphone"],
    "Computing": ["Wireless Mouse", "Mechanical Keyboard", "USB-C Hub",
                  "Laptop Stand", "Webcam", "External SSD"],
    "Home & Kitchen": ["Air Fryer", "Stand Mixer", "Electric Kettle",
                       "Coffee Grinder", "Vacuum Sealer", "Robot Vacuum"],
    "Cameras": ["Mirrorless Camera", "Action Camera", "Camera Tripod",
                "Ring Light", "Camera Backpack", "Drone"],
    "Gaming": ["Gaming Headset", "Gaming Mouse Pad", "Controller",
               "Gaming Chair", "RGB Keyboard", "Capture Card"],
    "Wearables": ["Fitness Tracker", "Smartwatch", "Sleep Tracker Ring",
                  "Heart Rate Monitor", "Smart Glasses"],
    "Accessories": ["Phone Case", "Screen Protector", "Charging Cable",
                    "Power Bank", "Wireless Charger", "Laptop Sleeve"],
    "Seasonal": ["Space Heater", "Tower Fan", "String Lights",
                 "Humidifier", "Dehumidifier", "Electric Blanket"],
}

BRANDS = [
    "Voltix", "Nimbus", "Cascade", "Northpeak", "Lumio", "Everline",
    "Fenwick", "Aurora Tech", "Driftwood", "Crestway", "Marlowe",
    "Bright Path", "Solace", "Ridgeline", "Kestrel",
]

US_STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

CA_PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"]


def _pick_locale(rng: random.Random) -> str:
    locales = list(_LOCALE_WEIGHTS.keys())
    weights = list(_LOCALE_WEIGHTS.values())
    return rng.choices(locales, weights=weights, k=1)[0]


def random_person_name(rng: random.Random | None = None) -> tuple[str, str, str]:
    """Return (first_name, last_name, locale) with occasional international/Unicode names."""
    rng = rng or random
    locale = _pick_locale(rng)
    faker = _fakers[locale]
    first = faker.first_name()
    last = faker.last_name()
    return first, last, locale


def random_email(first: str, last: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
               "icloud.com", "aol.com", "proton.me"]
    separators = ["", ".", "_"]
    first_ascii = first.encode("ascii", "ignore").decode() or "user"
    last_ascii = last.encode("ascii", "ignore").decode() or "customer"
    sep = rng.choice(separators)
    suffix = str(rng.randint(1, 999)) if rng.random() < 0.4 else ""
    local_part = f"{first_ascii}{sep}{last_ascii}{suffix}".lower()
    return f"{local_part}@{rng.choice(domains)}"


def random_phone(rng: random.Random | None = None, fmt: str | None = None) -> str:
    """Generate a phone number in one of 6+ common formats."""
    rng = rng or random
    area = rng.randint(200, 989)
    exchange = rng.randint(200, 989)
    line = rng.randint(1000, 9999)
    template = fmt or rng.choice([
        "({a}) {e}-{l}",
        "{a}-{e}-{l}",
        "{a}.{e}.{l}",
        "{a}{e}{l}",
        "+1 {a} {e} {l}",
        "1-{a}-{e}-{l}",
    ])
    return template.format(a=area, e=exchange, l=line)


def random_address(country: str = "US", rng: random.Random | None = None) -> dict:
    rng = rng or random
    faker = _fakers["en_CA"] if country == "CA" else _fakers["en_US"]
    region = rng.choice(CA_PROVINCES) if country == "CA" else rng.choice(US_STATES)
    postal = faker.postcode()
    line2 = ""
    if rng.random() < 0.3:
        unit = rng.choice(["Apt", "Unit", "Suite", "#"])
        line2 = f"{unit} {rng.randint(1, 400)}"
    return {
        "line1": faker.street_address(),
        "line2": line2,
        "city": faker.city(),
        "region": region,
        "postal_code": postal,
        "country": country,
    }


def random_product_name(category: str | None = None,
                         rng: random.Random | None = None) -> tuple[str, str]:
    """Return (category, product_name)."""
    rng = rng or random
    category = category or rng.choice(list(PRODUCT_CATEGORIES.keys()))
    base = rng.choice(PRODUCT_CATEGORIES[category])
    brand = rng.choice(BRANDS)
    return category, f"{brand} {base}"


def generate_shopify_sku(rng: random.Random | None = None) -> str:
    rng = rng or random
    return f"SH-{rng.randint(1000, 99999)}"


def generate_amazon_asin(rng: random.Random | None = None) -> str:
    rng = rng or random
    body = "".join(rng.choices(string.ascii_uppercase + string.digits, k=9))
    return f"B0{body}"[:10]


def generate_pos_internal_sku(rng: random.Random | None = None) -> str:
    rng = rng or random
    return f"POS-{rng.randint(10000, 99999)}"


def generate_order_id(prefix: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    return f"{prefix}-{rng.randint(10**8, 10**9 - 1)}"


def generate_ups_tracking(rng: random.Random | None = None) -> str:
    rng = rng or random
    digits = "".join(rng.choices(string.digits, k=16))
    return f"1Z{''.join(rng.choices(string.ascii_uppercase, k=3))}{digits}"[:18]


def generate_fedex_tracking(rng: random.Random | None = None) -> str:
    rng = rng or random
    return "".join(rng.choices(string.digits, k=12))


def generate_usps_tracking(rng: random.Random | None = None) -> str:
    rng = rng or random
    return "9400" + "".join(rng.choices(string.digits, k=18))
