"""Generates Shopify order-export CSV batches.

Mirrors a real Shopify "Export orders" CSV: one row per line item, with
order-level fields repeated on every line-item row (a simplification of
Shopify's real export, which blanks order-level fields on subsequent rows
for the same order — deliberately not replicated here to keep downstream
dedup logic testable without over-fitting to one export quirk).

Baseline Shopify-specific formatting only. Random corruption (encoding
issues, duplicate rows, mixed-case statuses, etc.) is layered on afterwards
by chaos_injector.py.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from src.simulator import fake_data_utils as fdu
from src.simulator import timeline as tl
from src.simulator.universe import Universe

FINANCIAL_STATUSES = ["paid", "pending", "refunded", "partially_refunded", "voided"]
FINANCIAL_STATUS_WEIGHTS = [0.80, 0.08, 0.06, 0.04, 0.02]
FULFILLMENT_STATUSES = ["fulfilled", "unfulfilled", "partial"]
FULFILLMENT_STATUS_WEIGHTS = [0.75, 0.15, 0.10]

DISCOUNT_TYPES = ["percentage", "fixed_amount", "free_shipping"]

BASE_COLUMNS = [
    "Name", "Email", "Financial Status", "Fulfillment Status", "Currency",
    "Created at", "Subtotal", "Shipping", "Taxes", "Total",
    "Discount Code", "Discount Amount",
    "Lineitem quantity", "Lineitem name", "Lineitem sku", "Lineitem price",
    "Billing Name", "Billing Address1", "Billing City", "Billing Province",
    "Billing Zip", "Billing Country",
    "Shipping Name", "Shipping Address1", "Shipping City", "Shipping Province",
    "Shipping Zip", "Shipping Country",
    "Phone",
]


def _new_order(order_number: int, universe: Universe, batch_dt: dt.datetime,
               rng: random.Random) -> dict:
    customers = universe.customers_for_channel("shopify")
    customer = rng.choice(customers)
    identity = customer.identities["shopify"]

    num_items = rng.choices([1, 2, 3], weights=[0.7, 0.22, 0.08], k=1)[0]
    products = rng.sample(universe.active_products(), k=min(num_items, len(universe.active_products())))
    line_items = [{"product": p, "quantity": rng.randint(1, 3)} for p in products]

    subtotal = sum(li["product"].retail_price * li["quantity"] for li in line_items)
    has_discount = rng.random() < 0.03
    discount_code = rng.choice(["WELCOME10", "SUMMER20", "SAVE15", "FREESHIP"]) if has_discount else ""
    discount_amount = round(subtotal * rng.uniform(0.05, 0.20), 2) if has_discount else 0.0
    shipping = 0.0 if (has_discount and discount_code == "FREESHIP") else round(rng.uniform(4.99, 14.99), 2)
    taxes = round((subtotal - discount_amount) * 0.0725, 2)
    total = round(subtotal - discount_amount + shipping + taxes, 2)

    is_international = rng.random() < 0.08
    country = "CA" if is_international else "US"
    address = fdu.random_address(country, rng)

    return {
        "order_number": order_number,
        "customer": customer,
        "identity": identity,
        "created_at": batch_dt,
        "financial_status": rng.choices(FINANCIAL_STATUSES, weights=FINANCIAL_STATUS_WEIGHTS, k=1)[0],
        "fulfillment_status": rng.choices(FULFILLMENT_STATUSES, weights=FULFILLMENT_STATUS_WEIGHTS, k=1)[0],
        "currency": "CAD" if country == "CA" else "USD",
        "subtotal": round(subtotal, 2),
        "shipping": shipping,
        "taxes": taxes,
        "total": total,
        "discount_code": discount_code,
        "discount_amount": discount_amount,
        "discount_type": rng.choice(DISCOUNT_TYPES) if has_discount else "",
        "line_items": line_items,
        "address": address,
    }


def generate_orders(universe: Universe, batch_dt: dt.datetime, num_orders: int,
                     rng: random.Random | None = None,
                     start_order_number: int = 100000) -> list[dict]:
    rng = rng or random.Random()
    return [_new_order(start_order_number + i, universe, batch_dt, rng)
            for i in range(num_orders)]


def orders_to_rows(orders: list[dict], include_discount_type: bool) -> list[dict]:
    rows = []
    for order in orders:
        identity = order["identity"]
        address = order["address"]
        full_name = f"{identity.first_name} {identity.last_name}"
        for li in order["line_items"]:
            row = {
                "Name": f"#{order['order_number']}",
                "Email": identity.email or "",
                "Financial Status": order["financial_status"],
                "Fulfillment Status": order["fulfillment_status"],
                "Currency": order["currency"],
                "Created at": order["created_at"].isoformat(),
                "Subtotal": order["subtotal"],
                "Shipping": order["shipping"],
                "Taxes": order["taxes"],
                "Total": order["total"],
                "Discount Code": order["discount_code"],
                "Discount Amount": order["discount_amount"],
                "Lineitem quantity": li["quantity"],
                "Lineitem name": li["product"].name,
                "Lineitem sku": li["product"].shopify_sku,
                "Lineitem price": li["product"].retail_price,
                "Billing Name": full_name,
                "Billing Address1": address["line1"],
                "Billing City": address["city"],
                "Billing Province": address["region"],
                "Billing Zip": address["postal_code"],
                "Billing Country": address["country"],
                "Shipping Name": full_name,
                "Shipping Address1": address["line1"],
                "Shipping City": address["city"],
                "Shipping Province": address["region"],
                "Shipping Zip": address["postal_code"],
                "Shipping Country": address["country"],
                "Phone": identity.phone or "",
            }
            if include_discount_type:
                row["Discount Type"] = order["discount_type"]
            rows.append(row)
    return rows


def write_csv(rows: list[dict], filepath: Path, include_discount_type: bool) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    columns = BASE_COLUMNS + (["Discount Type"] if include_discount_type else [])
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def generate_shopify_batch(universe: Universe, batch_dt: dt.datetime, num_orders: int,
                            output_dir: Path, rng: random.Random | None = None,
                            start_order_number: int = 100000) -> Path:
    rng = rng or random.Random()
    include_discount_type = tl.shopify_has_discount_type(batch_dt.date())
    orders = generate_orders(universe, batch_dt, num_orders, rng, start_order_number)
    rows = orders_to_rows(orders, include_discount_type)
    filename = f"shopify_batch_{batch_dt.strftime('%Y%m%d_%H')}.csv"
    filepath = Path(output_dir) / filename
    write_csv(rows, filepath, include_discount_type)
    return filepath
