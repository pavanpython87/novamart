"""The shared "universe" that every source simulator draws from.

A single source of truth ensures cross-channel consistency: the same
product has a matching Shopify SKU / Amazon ASIN / POS internal SKU across
all generators, and the same human being can show up as a slightly
different-looking customer record in Shopify, Amazon, and POS data (this is
what makes entity resolution in the pipeline meaningful).

Nothing here is deliberately "dirty" — degradation and format-specific
quirks are applied later by each source simulator and by
chaos_injector.py / quality_degrader.py.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.simulator import fake_data_utils as fdu

NUM_PRODUCTS = 200
NUM_CUSTOMERS = 5000
CROSS_CHANNEL_OVERLAP_PCT = 0.28  # ~28% of customers exist in 2+ channels

CHANNELS = ("shopify", "amazon", "pos")

# Amazon referral fee % by category (8-15%)
AMAZON_REFERRAL_FEE_PCT = {
    "Audio": 0.08,
    "Computing": 0.08,
    "Home & Kitchen": 0.15,
    "Cameras": 0.08,
    "Gaming": 0.15,
    "Wearables": 0.12,
    "Accessories": 0.15,
    "Seasonal": 0.15,
}

# Amazon FBA fulfillment fee tiers by weight (lbs) -> flat fee ($)
AMAZON_FBA_FEE_TIERS = [
    (1.0, 3.22),    # small standard, <= 1 lb
    (3.0, 4.75),    # large standard, <= 3 lb
    (10.0, 8.50),   # large standard, <= 10 lb
    (20.0, 12.75),  # small oversize
    (float("inf"), 19.99),  # large oversize
]

SHOPIFY_FEE_PCT = 0.029
SHOPIFY_FEE_FLAT = 0.30

POS_FEE_PCT = 0.026
POS_FEE_FLAT = 0.10

RETURN_RATES = {"amazon": 0.06, "shopify": 0.04, "pos": 0.02}

RETURN_REASON_CODES = {
    "no_longer_needed": 0.25,
    "wrong_item": 0.15,
    "defective": 0.20,
    "not_as_described": 0.15,
    "better_price_found": 0.10,
    "arrived_late": 0.05,
    "changed_mind": 0.10,
}


def amazon_fba_fee(weight_lbs: float) -> float:
    for threshold, fee in AMAZON_FBA_FEE_TIERS:
        if weight_lbs <= threshold:
            return fee
    return AMAZON_FBA_FEE_TIERS[-1][1]


@dataclass
class Product:
    product_id: str
    name: str
    category: str
    brand: str
    unit_cost: float
    retail_price: float
    weight_lbs: float
    dimensions_in: tuple[float, float, float]
    shopify_sku: str
    amazon_asin: str
    pos_internal_sku: str
    supplier: str
    is_active: bool = True

    @property
    def amazon_referral_fee_pct(self) -> float:
        return AMAZON_REFERRAL_FEE_PCT[self.category]

    @property
    def amazon_fba_fee(self) -> float:
        return amazon_fba_fee(self.weight_lbs)


@dataclass
class ChannelIdentity:
    """How one real person looks when represented within a single channel."""
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    address: dict
    loyalty_id: str | None = None


@dataclass
class Customer:
    customer_key: str
    channels: list[str]
    identities: dict[str, ChannelIdentity] = field(default_factory=dict)

    @property
    def is_cross_channel(self) -> bool:
        return len(self.channels) > 1


_SUPPLIERS = [
    "Pacific Rim Imports", "Continental Distributors", "Summit Wholesale",
    "Blue Harbor Trading", "Redwood Supply Co", "Meridian Goods",
    "Union Square Distribution", "Coastal Sourcing Group",
]


def _name_variant(first: str, last: str, rng: random.Random) -> tuple[str, str]:
    """Occasionally vary a name the way the same person might appear
    differently across systems (Bob vs Robert, middle initial, etc.)."""
    if rng.random() < 0.15:
        first = first[:1] + "."  # e.g. "R." instead of "Robert"
    elif rng.random() < 0.10 and len(first) > 3:
        first = first[:3]  # nickname-ish truncation
    if rng.random() < 0.10:
        last = f"{last} {rng.choice(list('ABCDEFGHJKLMNPQRSTUVWXYZ'))}."
    return first, last


class Universe:
    """Builds and holds the shared product catalog and customer pool."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.products: list[Product] = self._build_products()
        self.customers: list[Customer] = self._build_customers()

    # -- products ---------------------------------------------------
    def _build_products(self) -> list[Product]:
        products = []
        for i in range(1, NUM_PRODUCTS + 1):
            category, name = fdu.random_product_name(rng=self.rng)
            retail_price = round(self.rng.uniform(9.99, 499.99), 2)
            margin = self.rng.uniform(0.35, 0.65)
            unit_cost = round(retail_price * (1 - margin), 2)
            weight = round(self.rng.uniform(0.1, 25.0), 2)
            dims = (round(self.rng.uniform(2, 24), 1),
                    round(self.rng.uniform(2, 24), 1),
                    round(self.rng.uniform(1, 18), 1))
            products.append(Product(
                product_id=f"PROD-{i:06d}",
                name=name,
                category=category,
                brand=name.split()[0],
                unit_cost=unit_cost,
                retail_price=retail_price,
                weight_lbs=weight,
                dimensions_in=dims,
                shopify_sku=fdu.generate_shopify_sku(self.rng),
                amazon_asin=fdu.generate_amazon_asin(self.rng),
                pos_internal_sku=fdu.generate_pos_internal_sku(self.rng),
                supplier=self.rng.choice(_SUPPLIERS),
                is_active=self.rng.random() > 0.05,  # ~5% discontinued
            ))
        return products

    # -- customers ----------------------------------------------------
    def _build_customers(self) -> list[Customer]:
        customers = []
        num_overlap = int(NUM_CUSTOMERS * CROSS_CHANNEL_OVERLAP_PCT)
        for i in range(1, NUM_CUSTOMERS + 1):
            key = f"CUST-{i:06d}"
            first, last, _locale = fdu.random_person_name(self.rng)
            country = "CA" if self.rng.random() < 0.08 else "US"
            base_address = fdu.random_address(country, self.rng)

            is_overlap = i <= num_overlap
            channels = (self.rng.sample(CHANNELS, k=self.rng.choice([2, 3]))
                        if is_overlap else [self.rng.choice(CHANNELS)])

            identities: dict[str, ChannelIdentity] = {}
            for channel in channels:
                ch_first, ch_last = _name_variant(first, last, self.rng)
                identities[channel] = ChannelIdentity(
                    first_name=ch_first,
                    last_name=ch_last,
                    email=(fdu.random_email(first, last, self.rng)
                           if channel != "pos" or self.rng.random() < 0.6 else None),
                    phone=(fdu.random_phone(self.rng)
                           if channel != "amazon" or self.rng.random() < 0.3 else None),
                    address=base_address,
                    loyalty_id=(f"LOY-{self.rng.randint(100000, 999999)}"
                                if channel == "pos" and self.rng.random() < 0.6 else None),
                )
            customers.append(Customer(customer_key=key, channels=channels,
                                       identities=identities))
        return customers

    # -- convenience lookups -----------------------------------------
    def active_products(self) -> list[Product]:
        return [p for p in self.products if p.is_active]

    def customers_for_channel(self, channel: str) -> list[Customer]:
        return [c for c in self.customers if channel in c.channels]

    def sample_return_reason(self) -> str:
        reasons = list(RETURN_REASON_CODES.keys())
        weights = list(RETURN_REASON_CODES.values())
        return self.rng.choices(reasons, weights=weights, k=1)[0]
