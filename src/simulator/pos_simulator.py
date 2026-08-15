"""Generates POS (point-of-sale) transaction JSON files.

Simulates a Square/Toast-style transactions API dump. Structure changes at
month 12 of the historical timeline (POS system upgrade v3 -> v4):
  v3: transaction["items"] is a flat array at the transaction root.
  v4: transaction["line_items"] nests the items under a "line_items" object,
      and payment.card_type becomes payment.instrument.type.

Baseline POS-specific formatting only; random corruption (malformed JSON,
missing fields) is layered on afterwards by chaos_injector.py.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from src.simulator import timeline as tl
from src.simulator.universe import Universe

CARD_TYPES = ["visa", "mastercard", "amex", "discover"]
PAYMENT_METHOD_WEIGHTS = {"card": 0.55, "cash": 0.40, "employee_discount_card": 0.05}


def _new_transaction(txn_seq: int, universe: Universe, timestamp: dt.datetime,
                      rng: random.Random, use_v4: bool) -> dict:
    customers = universe.customers_for_channel("pos")
    customer = rng.choice(customers) if customers and rng.random() < 0.6 else None
    identity = customer.identities.get("pos") if customer else None

    num_items = rng.choices([1, 2, 3, 4], weights=[0.5, 0.3, 0.15, 0.05], k=1)[0]
    products = rng.sample(universe.active_products(), k=min(num_items, len(universe.active_products())))
    is_employee_discount = rng.random() < 0.05

    items = []
    subtotal = 0.0
    for p in products:
        qty = rng.randint(1, 2)
        unit_price = p.retail_price
        line_total = round(unit_price * qty, 2)
        subtotal += line_total
        item = {"sku": p.pos_internal_sku, "name": p.name, "quantity": qty,
                "unit_price": unit_price, "line_total": line_total}
        if is_employee_discount:
            item["employee_discount"] = round(unit_price * qty * 0.15, 2)
        items.append(item)

    tax = round(subtotal * 0.0725, 2)
    total = round(subtotal + tax, 2)

    payment_method = rng.choices(list(PAYMENT_METHOD_WEIGHTS.keys()),
                                  weights=list(PAYMENT_METHOD_WEIGHTS.values()), k=1)[0]
    if payment_method == "cash":
        tendered = round(total + rng.choice([0, 0.5, 1, 5, 10]), 2)
        payment = {"method": "cash", "amount_tendered": tendered,
                   "change_due": round(tendered - total, 2)}
    else:
        card_type = rng.choice(CARD_TYPES)
        last4 = f"{rng.randint(0, 9999):04d}"
        if use_v4:
            payment = {"method": "card", "instrument": {"type": card_type, "last4": last4}}
        else:
            payment = {"method": "card", "card_type": card_type, "last4": last4}

    transaction = {
        "transaction_id": f"TXN-{timestamp.strftime('%Y%m%d')}-{txn_seq:05d}",
        "timestamp": timestamp.isoformat(timespec="seconds"),  # local tz, no UTC offset
        "store_id": "STORE-01",
        "cashier_id": f"EMP-{rng.randint(1, 25):03d}",
        "payment": payment,
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "total": total,
        "loyalty_id": (identity.loyalty_id if identity else None),
    }
    if use_v4:
        transaction["line_items"] = {"items": items}
    else:
        transaction["items"] = items
    return transaction


def generate_transactions(universe: Universe, batch_dt: dt.datetime, num_transactions: int,
                           rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    use_v4 = tl.pos_v4_active(batch_dt.date())
    if tl.pos_v4_transition(batch_dt.date()):
        use_v4 = rng.random() < 0.5  # transition period: mixed v3/v4 days
    return [_new_transaction(i, universe, batch_dt, rng, use_v4) for i in range(num_transactions)]


def write_json(transactions: list[dict], filepath: Path, batch_dt: dt.datetime) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "store_id": "STORE-01",
        "batch_timestamp": batch_dt.isoformat(timespec="seconds"),
        "transaction_count": len(transactions),
        "transactions": transactions,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def generate_pos_batch(universe: Universe, batch_dt: dt.datetime, num_transactions: int,
                        output_dir: Path, rng: random.Random | None = None,
                        daily: bool = False) -> Path:
    rng = rng or random.Random()
    transactions = generate_transactions(universe, batch_dt, num_transactions, rng)
    if daily:
        filename = f"pos_transactions_{batch_dt.strftime('%Y_%m_%d')}.json"
    else:
        filename = f"pos_txn_{batch_dt.strftime('%Y%m%d_%H%M')}.json"
    filepath = Path(output_dir) / filename
    write_json(transactions, filepath, batch_dt)
    return filepath
