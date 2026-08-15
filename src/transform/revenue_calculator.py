"""Net revenue and gross profit calculation with full fee decomposition.

Operates on the canonical, post-cleaning order-line shape (one row per
order line, after validation/cleaning/dedup have already run):

    channel            "shopify" | "amazon" | "pos"
    category           product category (used for Amazon referral fee tier)
    gross_revenue      float, item_price * quantity before any deductions
    quantity           int
    weight_lbs         float, used for Amazon FBA fulfillment fee tier
    payment_method     "card" | "cash" | "employee_discount_card" | "paypal"
    discount_amount    float, coupon/bulk/employee discount already applied
    refund_amount      float, 0.0 if not returned
    restocking_fee     float, 0.0 if not applicable
    unit_cost          float, COGS per unit from supplier data

Fee constants mirror the real-world fee structures described in
PROJECT_PLAN.md section 5.6 (Amazon referral + FBA, Shopify transaction
fee, card/PayPal processing fees). They are redefined here rather than
imported from src.simulator.universe because the transform layer must
not depend on the simulator (it operates on real or simulated data
identically).
"""

from __future__ import annotations

import pandas as pd

# -- platform fees -------------------------------------------------------

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
DEFAULT_AMAZON_REFERRAL_FEE_PCT = 0.15

AMAZON_FBA_FEE_TIERS = [
    (1.0, 3.22),
    (3.0, 4.75),
    (10.0, 8.50),
    (20.0, 12.75),
    (float("inf"), 19.99),
]

SHOPIFY_FEE_PCT = 0.029
SHOPIFY_FEE_FLAT = 0.30

# -- payment processing fees ---------------------------------------------
# Charged on top of/alongside platform fees, based on how the customer paid.

PAYMENT_PROCESSING_FEE_PCT = {
    "card": 0.029,
    "employee_discount_card": 0.029,
    "paypal": 0.035,
    "cash": 0.0,
}
PAYMENT_PROCESSING_FEE_FLAT = {
    "card": 0.30,
    "employee_discount_card": 0.30,
    "paypal": 0.49,
    "cash": 0.0,
}
DEFAULT_PAYMENT_PROCESSING_FEE_PCT = 0.029
DEFAULT_PAYMENT_PROCESSING_FEE_FLAT = 0.30


def amazon_fba_fee(weight_lbs: float) -> float:
    """Flat FBA fulfillment fee for a given item weight tier."""
    for threshold, fee in AMAZON_FBA_FEE_TIERS:
        if weight_lbs <= threshold:
            return fee
    return AMAZON_FBA_FEE_TIERS[-1][1]


def calculate_platform_fee(
    channel: str, gross_revenue: float, category: str | None = None,
    weight_lbs: float | None = None,
) -> float:
    """Marketplace/platform fee charged by the selling channel itself.

    Amazon: referral fee (category-based %) + FBA fulfillment (weight-tiered
    flat fee). Shopify: flat-rate transaction fee (% + per-order flat).
    POS (in-store, no marketplace): no platform fee.
    """
    if channel == "amazon":
        referral_pct = AMAZON_REFERRAL_FEE_PCT.get(category, DEFAULT_AMAZON_REFERRAL_FEE_PCT)
        referral_fee = round(gross_revenue * referral_pct, 2)
        fba_fee = amazon_fba_fee(weight_lbs if weight_lbs is not None else 0.0)
        return round(referral_fee + fba_fee, 2)
    if channel == "shopify":
        return round(gross_revenue * SHOPIFY_FEE_PCT + SHOPIFY_FEE_FLAT, 2)
    return 0.0


def calculate_payment_processing_fee(payment_method: str | None, gross_revenue: float) -> float:
    """Payment processor fee (Stripe/PayPal/card-terminal-style), based on
    the tender type used, independent of which channel the sale came from.
    """
    if not payment_method:
        pct = DEFAULT_PAYMENT_PROCESSING_FEE_PCT
        flat = DEFAULT_PAYMENT_PROCESSING_FEE_FLAT
    else:
        pct = PAYMENT_PROCESSING_FEE_PCT.get(payment_method, DEFAULT_PAYMENT_PROCESSING_FEE_PCT)
        flat = PAYMENT_PROCESSING_FEE_FLAT.get(payment_method, DEFAULT_PAYMENT_PROCESSING_FEE_FLAT)
    if pct == 0.0 and flat == 0.0:
        return 0.0
    return round(gross_revenue * pct + flat, 2)


def calculate_net_revenue(order: dict) -> dict:
    """Full revenue decomposition for a single order line.

    Returns a dict with the original keys plus: platform_fee,
    payment_processing_fee, returns_and_refunds, discounts_and_promotions,
    net_revenue.
    """
    gross_revenue = float(order.get("gross_revenue") or 0.0)
    channel = order.get("channel")
    category = order.get("category")
    weight_lbs = order.get("weight_lbs")
    payment_method = order.get("payment_method")
    discount_amount = float(order.get("discount_amount") or 0.0)
    refund_amount = float(order.get("refund_amount") or 0.0)
    restocking_fee = float(order.get("restocking_fee") or 0.0)

    platform_fee = calculate_platform_fee(channel, gross_revenue, category, weight_lbs)
    payment_processing_fee = calculate_payment_processing_fee(payment_method, gross_revenue)
    returns_and_refunds = round(refund_amount - restocking_fee, 2)
    discounts_and_promotions = round(discount_amount, 2)

    net_revenue = round(
        gross_revenue
        - platform_fee
        - payment_processing_fee
        - returns_and_refunds
        - discounts_and_promotions,
        2,
    )

    return {
        **order,
        "platform_fee": platform_fee,
        "payment_processing_fee": payment_processing_fee,
        "returns_and_refunds": returns_and_refunds,
        "discounts_and_promotions": discounts_and_promotions,
        "net_revenue": net_revenue,
    }


def calculate_gross_profit(order: dict) -> dict:
    """Adds cogs and gross_profit to an order dict that already has
    net_revenue (i.e. has been through calculate_net_revenue)."""
    unit_cost = float(order.get("unit_cost") or 0.0)
    quantity = float(order.get("quantity") or 0.0)
    net_revenue = float(order.get("net_revenue") or 0.0)

    cogs = round(unit_cost * quantity, 2)
    gross_profit = round(net_revenue - cogs, 2)

    return {**order, "cogs": cogs, "gross_profit": gross_profit}


def calculate_order_economics(order: dict) -> dict:
    """Full pipeline: gross_revenue -> net_revenue -> gross_profit."""
    return calculate_gross_profit(calculate_net_revenue(order))


def calculate_order_economics_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized-by-row entry point for the pipeline: applies
    calculate_order_economics to every row of a canonical order-line
    DataFrame and returns a new DataFrame with the added economics columns.
    """
    if df.empty:
        columns = list(df.columns) + [
            "platform_fee", "payment_processing_fee", "returns_and_refunds",
            "discounts_and_promotions", "net_revenue", "cogs", "gross_profit",
        ]
        return pd.DataFrame(columns=columns)
    records = [calculate_order_economics(row.to_dict()) for _, row in df.iterrows()]
    return pd.DataFrame(records)
