"""Tests for the star-schema fact builders (shipping + inventory)."""

from __future__ import annotations

import datetime as dt
import random

import pandas as pd

from src.ingestion.registry import build_connector, load_sources
from src.load.fact_builders import (
    INVENTORY_COLUMNS,
    SHIPMENTS_COLUMNS,
    build_inventory_snapshot,
    build_shipments_fact,
)
from src.simulator.product_simulator import generate_product_catalog
from src.simulator.shipping_simulator import generate_shipping_batch
from src.simulator.universe import Universe


def _shipping_frames(tmp_path) -> dict[str, pd.DataFrame]:
    sources = load_sources()
    frames = {}
    for carrier in ("fedex", "ups", "usps"):
        path = generate_shipping_batch(carrier, dt.date(2024, 3, 1), 5, tmp_path,
                                        rng=random.Random(1))
        conn = build_connector(sources[f"shipping_{carrier}"], path)
        conn.connect()
        frames[f"shipping_{carrier}"] = conn.extract()
    return frames


def test_build_shipments_fact_standardizes_all_carriers(tmp_path):
    fact = build_shipments_fact(_shipping_frames(tmp_path))

    assert list(fact.columns) == SHIPMENTS_COLUMNS
    assert len(fact) == 15
    assert set(fact["carrier"]) == {"fedex", "ups", "usps"}
    assert fact["ship_date_key"].notna().all()
    assert fact["shipping_cost"].gt(0).all()


def test_build_shipments_fact_empty_frames():
    fact = build_shipments_fact({})
    assert list(fact.columns) == SHIPMENTS_COLUMNS
    assert fact.empty


def test_build_inventory_snapshot_is_deterministic(tmp_path):
    universe = Universe(seed=1)
    path = generate_product_catalog(universe, dt.date(2024, 3, 1), tmp_path,
                                     rng=random.Random(1))
    conn = build_connector(load_sources()["products"], path)
    conn.connect()
    products = conn.extract()

    first = build_inventory_snapshot(products, snapshot_date=dt.date(2024, 3, 1))
    second = build_inventory_snapshot(products, snapshot_date=dt.date(2024, 3, 1))

    assert list(first.columns) == INVENTORY_COLUMNS
    assert len(first) > 0
    assert first["product_key"].is_unique
    assert (first["on_hand_qty"] >= 10).all()
    assert (first["lead_time_days"] >= 3).all()
    # Deterministic across calls (and across processes, unlike hash()).
    assert first["on_hand_qty"].tolist() == second["on_hand_qty"].tolist()


def test_build_inventory_snapshot_empty():
    snap = build_inventory_snapshot(pd.DataFrame())
    assert list(snap.columns) == INVENTORY_COLUMNS
    assert snap.empty
