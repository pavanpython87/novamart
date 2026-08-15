"""Generates the weekly customer sync CSV.

Each row is one per-channel identity (a person can appear multiple times
in a single file if they exist in 2+ channels and multiple of their
channel identities changed that week). Amazon identities often have no
phone; POS identities often have no email — matching the shared universe's
identity model in universe.py.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from src.simulator.universe import Universe

COLUMNS = [
    "customer_id", "channel", "sync_type", "first_name", "last_name",
    "email", "phone", "address_line1", "address_line2", "city", "region",
    "postal_code", "country", "loyalty_id",
]


def _rows_for_customer(customer, sync_type: str) -> list[dict]:
    rows = []
    for channel, identity in customer.identities.items():
        rows.append({
            "customer_id": customer.customer_key,
            "channel": channel,
            "sync_type": sync_type,
            "first_name": identity.first_name,
            "last_name": identity.last_name,
            "email": identity.email or "",
            "phone": identity.phone or "",
            "address_line1": identity.address["line1"],
            "address_line2": identity.address["line2"],
            "city": identity.address["city"],
            "region": identity.address["region"],
            "postal_code": identity.address["postal_code"],
            "country": identity.address["country"],
            "loyalty_id": identity.loyalty_id or "",
        })
    return rows


def build_sync_rows(universe: Universe, rng: random.Random,
                     num_new: int, num_updated: int) -> list[dict]:
    pool = universe.customers
    sample_size = min(num_new + num_updated, len(pool))
    sample = rng.sample(pool, k=sample_size)
    new_customers, updated_customers = sample[:num_new], sample[num_new:]

    rows = []
    for c in new_customers:
        rows.extend(_rows_for_customer(c, "new"))
    for c in updated_customers:
        rows.extend(_rows_for_customer(c, "updated"))
    return rows


def write_csv(rows: list[dict], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def generate_customer_sync(universe: Universe, sync_date, output_dir: Path,
                            rng: random.Random | None = None,
                            num_new: int | None = None,
                            num_updated: int = 50) -> Path:
    rng = rng or random.Random()
    num_new = num_new if num_new is not None else rng.randint(200, 400)
    rows = build_sync_rows(universe, rng, num_new, num_updated)
    filename = f"customer_sync_{sync_date.strftime('%Y%m%d')}.csv"
    filepath = Path(output_dir) / filename
    write_csv(rows, filepath)
    return filepath
