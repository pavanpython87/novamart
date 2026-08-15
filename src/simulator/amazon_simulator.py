"""Generates Amazon marketplace settlement XLSX workbooks.

Four sheets per file: Orders, Returns, Fee Breakdown, Adjustments — matching
a typical Amazon Seller Central settlement export. Baseline Amazon-specific
formatting only (fee structure, ASIN format, sheet layout); random
corruption (merged cells, formula errors, sign-convention flips) is layered
on afterwards by chaos_injector.py.
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

import pandas as pd

from src.simulator import timeline as tl
from src.simulator.universe import RETURN_RATES, Universe

ORDER_STATUSES = ["Shipped", "Pending", "Cancelled", "Refunded"]
ORDER_STATUS_WEIGHTS = [0.85, 0.06, 0.04, 0.05]

ADJUSTMENT_REASONS = ["Warehouse Damage", "Lost Inventory", "Chargeback",
                       "Customer Service Concession", "Reimbursement"]


def _new_order(order_seq: int, universe: Universe, order_date: dt.date,
               rng: random.Random) -> dict:
    customers = universe.customers_for_channel("amazon")
    customer = rng.choice(customers)
    identity = customer.identities["amazon"]
    product = rng.choice(universe.active_products())
    quantity = rng.choices([1, 2, 3], weights=[0.8, 0.15, 0.05], k=1)[0]

    item_price = round(product.retail_price * quantity, 2)
    referral_fee = round(item_price * product.amazon_referral_fee_pct, 2)
    fba_fee = product.amazon_fba_fee

    return {
        "amazon_order_id": f"111-{rng.randint(1000000, 9999999)}-{rng.randint(1000000, 9999999)}",
        "asin": product.amazon_asin,
        "sku": product.pos_internal_sku,  # Amazon seller SKU often mirrors internal SKU
        "product_name": product.name,
        "quantity": quantity,
        "item_price": item_price,
        "order_date": order_date,
        "ship_date": order_date + dt.timedelta(days=rng.randint(0, 2)),
        "order_status": rng.choices(ORDER_STATUSES, weights=ORDER_STATUS_WEIGHTS, k=1)[0],
        "customer_name": f"{identity.first_name} {identity.last_name}",
        "referral_fee": referral_fee,
        "fba_fee": fba_fee,
        "product": product,
        "customer": customer,
    }


def generate_orders(universe: Universe, order_date: dt.date, num_orders: int,
                     rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    return [_new_order(i, universe, order_date, rng) for i in range(num_orders)]


def build_orders_sheet(orders: list[dict], fee_column_renamed: bool) -> pd.DataFrame:
    fee_col = "referral_fee_amount" if fee_column_renamed else "referral_fee"
    rows = []
    for o in orders:
        rows.append({
            "amazon-order-id": o["amazon_order_id"],
            "asin": o["asin"],
            "sku": o["sku"],
            "product-name": o["product_name"],
            "quantity": o["quantity"],
            "item-price": o["item_price"],
            "purchase-date": o["order_date"].isoformat(),
            "ship-date": o["ship_date"].isoformat(),
            "order-status": o["order_status"],
            "buyer-name": o["customer_name"],
            fee_col: o["referral_fee"],
            "fba-fee": o["fba_fee"],
        })
    return pd.DataFrame(rows)


def build_returns_sheet(orders: list[dict], universe: Universe,
                         rng: random.Random) -> pd.DataFrame:
    shipped = [o for o in orders if o["order_status"] == "Shipped"]
    n_returns = int(len(shipped) * RETURN_RATES["amazon"])
    returned = rng.sample(shipped, k=min(n_returns, len(shipped)))
    rows = []
    for o in returned:
        refund_amount = round(o["item_price"] * rng.uniform(0.9, 1.0), 2)
        rows.append({
            "amazon-order-id": o["amazon_order_id"],
            "asin": o["asin"],
            "return-date": (o["order_date"] + dt.timedelta(days=rng.randint(2, 21))).isoformat(),
            "return-reason": universe.sample_return_reason(),
            "refund-amount": refund_amount,
            "refund-type": rng.choice(["full", "partial"]),
            "restocking-fee": round(refund_amount * 0.1, 2) if rng.random() < 0.15 else 0.0,
        })
    return pd.DataFrame(rows)


def build_fee_breakdown_sheet(orders: list[dict], fee_column_renamed: bool) -> pd.DataFrame:
    fee_col = "referral_fee_amount" if fee_column_renamed else "referral_fee"
    rows = []
    for o in orders:
        rows.append({"amazon-order-id": o["amazon_order_id"], "fee-type": "ReferralFee",
                      fee_col: o["referral_fee"]})
        rows.append({"amazon-order-id": o["amazon_order_id"], "fee-type": "FBAFulfillmentFee",
                      fee_col: o["fba_fee"]})
    return pd.DataFrame(rows)


def build_adjustments_sheet(orders: list[dict], rng: random.Random) -> pd.DataFrame:
    n_adjustments = max(1, int(len(orders) * 0.01))
    sample = rng.sample(orders, k=min(n_adjustments, len(orders)))
    rows = [{
        "amazon-order-id": o["amazon_order_id"],
        "adjustment-date": (o["order_date"] + dt.timedelta(days=rng.randint(1, 30))).isoformat(),
        "adjustment-reason": rng.choice(ADJUSTMENT_REASONS),
        "adjustment-amount": round(rng.uniform(-50, -1), 2),
    } for o in sample]
    return pd.DataFrame(rows)


def write_workbook(sheets: dict[str, pd.DataFrame], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)


def generate_amazon_batch(universe: Universe, order_date: dt.date, num_orders: int,
                           output_dir: Path, rng: random.Random | None = None) -> Path:
    rng = rng or random.Random()
    fee_column_renamed = tl.amazon_fee_column_renamed(order_date)
    orders = generate_orders(universe, order_date, num_orders, rng)

    sheets = {
        "Orders": build_orders_sheet(orders, fee_column_renamed),
        "Returns": build_returns_sheet(orders, universe, rng),
        "Fee Breakdown": build_fee_breakdown_sheet(orders, fee_column_renamed),
        "Adjustments": build_adjustments_sheet(orders, rng),
    }
    filename = f"amazon_daily_{order_date.strftime('%Y%m%d')}.xlsx"
    filepath = Path(output_dir) / filename
    write_workbook(sheets, filepath)
    return filepath
