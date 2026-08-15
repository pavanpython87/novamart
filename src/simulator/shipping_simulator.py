"""Generates multi-carrier shipping feeds: FedEx (XML), UPS (CSV, no header),
USPS (pipe-delimited text).

Each carrier gets its own tracking-number format, status-code vocabulary,
weight unit, and date format — deliberately different from each other, the
way three real carriers' exports would be. This is the "three completely
different schemas for the same entity" scenario the pipeline's shipping
connectors must reconcile.
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path
from xml.etree import ElementTree as ET

from src.simulator import fake_data_utils as fdu

CARRIERS = ("fedex", "ups", "usps")

FEDEX_STATUS = {"delivered": "DELIVERED", "in_transit": "IN_TRANSIT",
                "pending": "PENDING", "exception": "EXCEPTION"}
UPS_STATUS = {"delivered": "D", "in_transit": "I", "pending": "P", "exception": "X"}
USPS_STATUS = {"delivered": "DELIVERED", "in_transit": "IN_TRANSIT",
               "pending": "PRE_TRANSIT", "exception": "ALERT"}

PROMISED_DAYS = {"fedex": 3, "ups": 4, "usps": 5}

LBS_TO_KG = 0.453592
LBS_TO_OZ = 16.0


def _new_shipment(carrier: str, ship_date: dt.date, rng: random.Random) -> dict:
    promised = PROMISED_DAYS[carrier]
    weight_lbs = round(rng.uniform(0.2, 25.0), 2)

    outcome = rng.random()
    if outcome < 0.03:
        status = "exception"
        delivery_date = None
        actual_days = None
    elif outcome < 0.15:
        status = "delivered"
        actual_days = promised + rng.randint(1, 4)  # late but delivered
        delivery_date = ship_date + dt.timedelta(days=actual_days)
    else:
        status = "delivered"
        actual_days = rng.randint(1, promised)
        delivery_date = ship_date + dt.timedelta(days=actual_days)

    tracking_fn = {"fedex": fdu.generate_fedex_tracking,
                   "ups": fdu.generate_ups_tracking,
                   "usps": fdu.generate_usps_tracking}[carrier]

    return {
        "carrier": carrier,
        "tracking_number": tracking_fn(rng),
        "reference_order_id": f"ORD-{rng.randint(10**7, 10**8 - 1)}",
        "ship_date": ship_date,
        "delivery_date": delivery_date,
        "promised_days": promised,
        "status": status,
        "weight_lbs": weight_lbs,
    }


def generate_shipments(carrier: str, ship_date: dt.date, num_shipments: int,
                        rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    return [_new_shipment(carrier, ship_date, rng) for _ in range(num_shipments)]


# -- per-carrier writers -------------------------------------------------

def write_fedex_xml(shipments: list[dict], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    ns = "http://fedex.com/ship"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}Shipments")
    for s in shipments:
        el = ET.SubElement(root, f"{{{ns}}}Shipment")
        ET.SubElement(el, f"{{{ns}}}TrackingNumber").text = s["tracking_number"]
        ET.SubElement(el, f"{{{ns}}}OrderId").text = s["reference_order_id"]
        ET.SubElement(el, f"{{{ns}}}ShipDate").text = s["ship_date"].isoformat()
        ET.SubElement(el, f"{{{ns}}}DeliveryDate").text = (
            s["delivery_date"].isoformat() if s["delivery_date"] else "")
        ET.SubElement(el, f"{{{ns}}}Status").text = FEDEX_STATUS[s["status"]]
        ET.SubElement(el, f"{{{ns}}}WeightLbs").text = str(s["weight_lbs"])
    ET.ElementTree(root).write(filepath, encoding="utf-8", xml_declaration=True)


def write_ups_csv(shipments: list[dict], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        for s in shipments:
            weight_kg = round(s["weight_lbs"] * LBS_TO_KG, 2)
            delivery = s["delivery_date"].strftime("%m/%d/%Y") if s["delivery_date"] else ""
            f.write(",".join([
                s["tracking_number"],
                s["reference_order_id"],
                s["ship_date"].strftime("%m/%d/%Y"),
                delivery,
                UPS_STATUS[s["status"]],
                str(weight_kg),
            ]) + "\n")


def write_usps_txt(shipments: list[dict], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for s in shipments:
            weight_oz = round(s["weight_lbs"] * LBS_TO_OZ, 1)
            delivery = s["delivery_date"].strftime("%Y%m%d") if s["delivery_date"] else ""
            f.write("|".join([
                s["tracking_number"],
                s["reference_order_id"],
                s["ship_date"].strftime("%Y%m%d"),
                delivery,
                USPS_STATUS[s["status"]],
                str(weight_oz),
            ]) + "\n")


_WRITERS = {"fedex": write_fedex_xml, "ups": write_ups_csv, "usps": write_usps_txt}
_EXTENSIONS = {"fedex": "xml", "ups": "csv", "usps": "txt"}


def generate_shipping_batch(carrier: str, ship_date: dt.date, num_shipments: int,
                             output_dir: Path, rng: random.Random | None = None) -> Path:
    rng = rng or random.Random()
    if carrier not in CARRIERS:
        raise ValueError(f"Unknown carrier: {carrier}")
    shipments = generate_shipments(carrier, ship_date, num_shipments, rng)
    ext = _EXTENSIONS[carrier]
    filename = f"{carrier}_{ship_date.strftime('%Y%m%d')}.{ext}"
    filepath = Path(output_dir) / filename
    _WRITERS[carrier](shipments, filepath)
    return filepath
