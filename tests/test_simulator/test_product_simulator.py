import datetime as dt
import random
import sqlite3

from src.simulator.product_simulator import generate_product_catalog
from src.simulator.universe import Universe

UNIVERSE = Universe(seed=1)


def test_generate_product_catalog_creates_sqlite(tmp_path):
    path = generate_product_catalog(UNIVERSE, dt.date(2024, 2, 1), tmp_path,
                                      rng=random.Random(1))
    assert path.exists()
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    assert len(rows) >= len(UNIVERSE.products)  # includes some duplicate rows


def test_catalog_has_missing_categories_and_costs(tmp_path):
    path = generate_product_catalog(UNIVERSE, dt.date(2024, 2, 1), tmp_path,
                                      rng=random.Random(2))
    conn = sqlite3.connect(path)
    total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    null_category = conn.execute(
        "SELECT COUNT(*) FROM products WHERE category IS NULL").fetchone()[0]
    null_cost = conn.execute(
        "SELECT COUNT(*) FROM products WHERE supplier_cost IS NULL").fetchone()[0]
    conn.close()
    assert null_category > 0
    assert null_cost > 0
    assert null_category / total < 0.30  # sanity bound around configured 15%


def test_catalog_has_mixed_weight_units(tmp_path):
    path = generate_product_catalog(UNIVERSE, dt.date(2024, 2, 1), tmp_path,
                                      rng=random.Random(3))
    conn = sqlite3.connect(path)
    units = {row[0] for row in conn.execute(
        "SELECT DISTINCT weight_unit FROM products").fetchall()}
    conn.close()
    assert units.issubset({"lbs", "kg", None})
    assert len(units) > 1


def test_catalog_filename_pattern(tmp_path):
    path = generate_product_catalog(UNIVERSE, dt.date(2024, 3, 15), tmp_path,
                                      rng=random.Random(4))
    assert path.name == "catalog_20240315.db"
