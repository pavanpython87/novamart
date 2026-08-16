"""Builds star-schema fact DataFrames from raw/clean ingested source frames.

Two facts the dashboards read are derived here:

  - fact_shipments        from the three carrier feeds (FedEx XML, UPS CSV,
                           USPS flat file), standardized to one canonical
                           shape and given a shipping-cost estimate from weight.
  - fact_inventory_daily   from the monthly product catalog. The catalog
                           doesn't carry stock levels, so on_hand_qty and
                           lead_time_days are a deterministic, seeded snapshot
                           derived from product_id (stable across runs) — the
                           load-layer equivalent of the simulator's realistic
                           fake data.

Both return DataFrames whose columns exactly match schema_manager.TABLE_SCHEMAS
(and therefore DuckDBLoader.upsert's positional INSERT).
"""

from __future__ import annotations

import datetime as dt
import hashlib

import pandas as pd

SHIPMENTS_COLUMNS = ["tracking_number", "order_id", "carrier",
                     "ship_date_key", "delivery_date_key", "shipping_cost"]
INVENTORY_COLUMNS = ["product_key", "snapshot_date_key", "on_hand_qty", "lead_time_days"]

LBS_TO_KG = 0.453592
OZ_TO_KG = 0.0283495

# Simple carrier cost model: a base fee plus a per-kg rate. Deliberately
# approximate — the source feeds carry weight, not price, and this gives
# the shipping dashboard a comparable cost figure per carrier.
CARRIER_WEIGHT_UNIT = {"fedex": "lbs", "ups": "kg", "usps": "oz"}
CARRIER_BASE_COST = {"fedex": 8.0, "ups": 7.0, "usps": 5.0}
CARRIER_PER_KG = {"fedex": 1.5, "ups": 1.2, "usps": 2.8}

_CARRIER_COLUMNS = {
    "fedex": {"tracking": "TrackingNumber", "order_id": "OrderId", "ship_date": "ShipDate",
              "delivery_date": "DeliveryDate", "weight": "WeightLbs"},
    "ups": {"tracking": "tracking_number", "order_id": "reference_order_id",
            "ship_date": "ship_date", "delivery_date": "delivery_date", "weight": "weight_kg"},
    "usps": {"tracking": "tracking_number", "order_id": "reference_order_id",
             "ship_date": "ship_date", "delivery_date": "delivery_date", "weight": "weight_oz"},
}

_WEIGHT_TO_KG = {"lbs": LBS_TO_KG, "kg": 1.0, "oz": OZ_TO_KG}


def _stable_int(key: str, modulus: int) -> int:
    """Deterministic integer in [0, modulus) for a string key — stable
    across processes, unlike Python's built-in hash()."""
    digest = hashlib.md5(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % modulus


def _to_dates(series: pd.Series) -> list:
    """Converts a series of date strings (ISO, MM/DD/YYYY, YYYYMMDD) to
    Python date objects, None for unparseable/empty values."""
    parsed = pd.to_datetime(series, errors="coerce")
    return [v.date() if pd.notna(v) else None for v in parsed]


def _standardize_carrier(carrier: str, df: pd.DataFrame) -> pd.DataFrame:
    columns = _CARRIER_COLUMNS[carrier]
    if df is None or df.empty or columns["tracking"] not in df.columns:
        return pd.DataFrame(columns=SHIPMENTS_COLUMNS)

    out = pd.DataFrame()
    out["tracking_number"] = df[columns["tracking"]].astype(str)
    out["order_id"] = df[columns["order_id"]].astype(str)
    out["carrier"] = carrier
    out["ship_date_key"] = _to_dates(df[columns["ship_date"]])
    out["delivery_date_key"] = _to_dates(df[columns["delivery_date"]])

    weight = pd.to_numeric(df[columns["weight"]], errors="coerce").fillna(0.0)
    kg = weight * _WEIGHT_TO_KG[CARRIER_WEIGHT_UNIT[carrier]]
    out["shipping_cost"] = (CARRIER_BASE_COST[carrier] + kg * CARRIER_PER_KG[carrier]).round(2)
    return out


def build_shipments_fact(clean_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Standardizes all three carrier feeds into the fact_shipments shape."""
    frames = []
    for carrier in ("fedex", "ups", "usps"):
        df = clean_frames.get(f"shipping_{carrier}")
        if df is not None and not df.empty:
            frames.append(_standardize_carrier(carrier, df))

    if not frames:
        return pd.DataFrame(columns=SHIPMENTS_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def build_inventory_snapshot(products_df: pd.DataFrame,
                             snapshot_date: dt.date | None = None) -> pd.DataFrame:
    """Builds one fact_inventory_daily row per catalog product.

    on_hand_qty and lead_time_days are seeded deterministically from
    product_id (the source catalog has no stock columns)."""
    if products_df is None or products_df.empty or "product_id" not in products_df.columns:
        return pd.DataFrame(columns=INVENTORY_COLUMNS)

    snapshot_date = snapshot_date or dt.date.today()
    rows = []
    seen: set[str] = set()
    for rec in products_df.to_dict("records"):
        product_id = str(rec.get("product_id") or "").strip()
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        rows.append({
            "product_key": product_id,
            "snapshot_date_key": snapshot_date,
            "on_hand_qty": 10 + _stable_int(product_id, 490),
            "lead_time_days": 3 + _stable_int(f"{product_id}:lt", 19),
        })

    return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)
