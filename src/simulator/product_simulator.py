"""Generates the monthly product catalog export as a SQLite database.

Baseline catalog data comes from the shared universe (clean, consistent
IDs/SKUs). This module applies the catalog-specific data-quality issues
called out in the project plan (missing categories, missing supplier
costs, mixed weight units, mislabeled discontinued products, and a
handful of near-duplicate rows) since these are intrinsic to how the
catalog export tool behaves, not random per-batch chaos.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

from src.simulator.universe import Universe

MISSING_CATEGORY_RATE = 0.15
MISSING_SUPPLIER_COST_RATE = 0.20
MISLABELED_DISCONTINUED_RATE = 0.30  # of truly-inactive products, how many still say active
DUPLICATE_ROW_RATE = 0.02

WEIGHT_UNITS = ["lbs", "kg", None]  # None = unit omitted entirely (ambiguous)
LBS_TO_KG = 0.453592


def _catalog_rows(universe: Universe, rng: random.Random) -> list[dict]:
    rows = []
    for p in universe.products:
        category = None if rng.random() < MISSING_CATEGORY_RATE else p.category
        supplier_cost = None if rng.random() < MISSING_SUPPLIER_COST_RATE else p.unit_cost

        unit = rng.choice(WEIGHT_UNITS)
        weight_value = round(p.weight_lbs * LBS_TO_KG, 2) if unit == "kg" else p.weight_lbs

        is_active = p.is_active
        if not p.is_active and rng.random() < MISLABELED_DISCONTINUED_RATE:
            is_active = True  # discontinued product still marked active — data quality bug

        rows.append({
            "product_id": p.product_id,
            "name": p.name,
            "category": category,
            "brand": p.brand,
            "supplier": p.supplier,
            "supplier_cost": supplier_cost,
            "retail_price": p.retail_price,
            "weight_value": weight_value,
            "weight_unit": unit,
            "shopify_sku": p.shopify_sku,
            "amazon_asin": p.amazon_asin,
            "pos_internal_sku": p.pos_internal_sku,
            "is_active": int(is_active),
        })

    # Duplicate a small number of rows with a name variation
    duplicatable = [r for r in rows if rng.random() < DUPLICATE_ROW_RATE]
    for r in duplicatable:
        dup = dict(r)
        dup["product_id"] = f"{r['product_id']}-DUP"
        dup["name"] = f"{r['name']} "  # trailing whitespace variant
        rows.append(dup)

    return rows


def write_sqlite(rows: list[dict], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if filepath.exists():
        filepath.unlink()
    conn = sqlite3.connect(filepath)
    try:
        conn.execute("""
            CREATE TABLE products (
                product_id TEXT,
                name TEXT,
                category TEXT,
                brand TEXT,
                supplier TEXT,
                supplier_cost REAL,
                retail_price REAL,
                weight_value REAL,
                weight_unit TEXT,
                shopify_sku TEXT,
                amazon_asin TEXT,
                pos_internal_sku TEXT,
                is_active INTEGER
            )
        """)
        conn.executemany(
            """INSERT INTO products VALUES
               (:product_id, :name, :category, :brand, :supplier, :supplier_cost,
                :retail_price, :weight_value, :weight_unit, :shopify_sku, :amazon_asin,
                :pos_internal_sku, :is_active)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def generate_product_catalog(universe: Universe, export_date, output_dir: Path,
                              rng: random.Random | None = None) -> Path:
    rng = rng or random.Random()
    rows = _catalog_rows(universe, rng)
    filename = f"catalog_{export_date.strftime('%Y%m%d')}.db"
    filepath = Path(output_dir) / filename
    write_sqlite(rows, filepath)
    return filepath
