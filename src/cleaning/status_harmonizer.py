"""Maps source-specific status vocabularies to a small unified set, so
downstream analytics don't need to special-case each channel's status
strings.

Two domains are harmonized:
  - order status (Shopify financial/fulfillment statuses, Amazon
    order-status) -> {pending, paid, shipped, unfulfilled,
    partially_shipped, cancelled, refunded, partially_refunded}
  - shipment status (FedEx/USPS text codes, UPS single-letter codes)
    -> {pending, in_transit, delivered, exception}
"""

from __future__ import annotations

_ORDER_STATUS_MAP = {
    # Shopify financial_status
    "paid": "paid", "pending": "pending", "refunded": "refunded",
    "partially_refunded": "partially_refunded", "voided": "cancelled",
    # Shopify fulfillment_status
    "fulfilled": "shipped", "unfulfilled": "unfulfilled", "partial": "partially_shipped",
    # Amazon order-status
    "shipped": "shipped", "cancelled": "cancelled",
}

_SHIPMENT_STATUS_MAP = {
    "delivered": "delivered", "d": "delivered",
    "in_transit": "in_transit", "i": "in_transit",
    "pending": "pending", "p": "pending", "pre_transit": "pending",
    "exception": "exception", "x": "exception", "alert": "exception",
}


def harmonize_order_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _ORDER_STATUS_MAP.get(str(raw).strip().lower())


def harmonize_shipment_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _SHIPMENT_STATUS_MAP.get(str(raw).strip().lower())
