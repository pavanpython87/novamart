"""Default per-source configuration for orchestration: how each raw
ingested source maps onto the canonical order-line shape
(src.transform.revenue_calculator) and which quality_rules.yaml entry
each source is validated against.

These are deliberately just *defaults* — callers of the transform tasks
can still pass their own field_map (see transform_tasks.map_to_canonical_orders)
for cases these don't cover.
"""

from __future__ import annotations

# Only channels that actually generate order-line revenue are mapped here;
# products/customers/shipping sources feed dimension/fact tables this
# phase's orchestration doesn't build yet (see PROJECT_PLAN Phase 5 scope).
CANONICAL_FIELD_MAPS: dict[str, dict[str, str]] = {
    "shopify": {
        "order_id": "Name",
        "customer_key": "Email",
        "customer_email": "Email",
        "order_date": "Created at",
        "gross_revenue": "Total",
        "quantity": "Lineitem quantity",
        "discount_amount": "Discount Amount",
        "product_key": "Lineitem sku",
        "status": "Financial Status",
    },
    "amazon": {
        "order_id": "amazon-order-id",
        "customer_key": "buyer-name",
        "order_date": "purchase-date",
        "gross_revenue": "item-price",
        "quantity": "quantity",
        "product_key": "asin",
        "status": "order-status",
    },
    "pos": {
        "order_id": "transaction_id",
        "customer_key": "loyalty_id",
        "order_date": "timestamp",
        "gross_revenue": "line_total",
        "quantity": "quantity",
        "product_key": "sku",
        "payment_method": "payment.method",
    },
}

# Deduplication keys per channel, expressed in each source's *raw* column
# names (dedup runs before canonical mapping). Line-item sources must key
# on order + product so multi-line orders aren't collapsed to one row.
DEDUP_KEYS: dict[str, list[str]] = {
    "shopify": ["Name", "Lineitem sku"],
    "amazon": ["amazon-order-id", "asin"],
    "pos": ["transaction_id", "sku"],
}

CANONICAL_DEFAULTS: dict[str, dict] = {
    "shopify": {"payment_method": "card", "refund_amount": 0.0, "restocking_fee": 0.0, "unit_cost": 0.0},
    "amazon": {"payment_method": "card", "refund_amount": 0.0, "restocking_fee": 0.0, "unit_cost": 0.0,
               "discount_amount": 0.0},
    "pos": {"refund_amount": 0.0, "restocking_fee": 0.0, "unit_cost": 0.0, "discount_amount": 0.0},
}

ORDER_SOURCES = tuple(CANONICAL_FIELD_MAPS.keys())

# quality_rules.yaml keys its "shipping" rules once, shared by all three
# shipping carriers.
SOURCE_TO_RULES_KEY: dict[str, str] = {
    "shipping_fedex": "shipping",
    "shipping_ups": "shipping",
    "shipping_usps": "shipping",
}


def rules_key_for_source(source_name: str) -> str:
    return SOURCE_TO_RULES_KEY.get(source_name, source_name)
