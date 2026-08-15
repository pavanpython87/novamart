import datetime as dt
import random
from xml.etree import ElementTree as ET

from src.simulator.shipping_simulator import generate_shipping_batch

SHIP_DATE = dt.date(2024, 6, 1)


def test_fedex_xml_output(tmp_path):
    path = generate_shipping_batch("fedex", SHIP_DATE, 10, tmp_path, rng=random.Random(1))
    assert path.suffix == ".xml"
    tree = ET.parse(path)
    ns = {"f": "http://fedex.com/ship"}
    shipments = tree.getroot().findall("f:Shipment", ns)
    assert len(shipments) == 10


def test_ups_csv_no_header(tmp_path):
    path = generate_shipping_batch("ups", SHIP_DATE, 10, tmp_path, rng=random.Random(2))
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 10
    first_cols = lines[0].split(",")
    assert first_cols[0].startswith("1Z")  # tracking number, not a header


def test_usps_pipe_delimited(tmp_path):
    path = generate_shipping_batch("usps", SHIP_DATE, 10, tmp_path, rng=random.Random(3))
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 10
    assert lines[0].startswith("9400")
    assert lines[0].count("|") == 5


def test_unknown_carrier_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        generate_shipping_batch("dhl", SHIP_DATE, 5, tmp_path)


def test_weight_units_differ_by_carrier(tmp_path):
    fedex_path = generate_shipping_batch("fedex", SHIP_DATE, 5, tmp_path, rng=random.Random(9))
    ups_path = generate_shipping_batch("ups", SHIP_DATE, 5, tmp_path, rng=random.Random(9))
    usps_path = generate_shipping_batch("usps", SHIP_DATE, 5, tmp_path, rng=random.Random(9))
    # Same rng seed -> same underlying weight_lbs, but written in different units
    fedex_weight = float(ET.parse(fedex_path).getroot()[0].find(
        "{http://fedex.com/ship}WeightLbs").text)
    ups_weight_kg = float(ups_path.read_text().split("\n")[0].split(",")[-1])
    usps_weight_oz = float(usps_path.read_text().split("\n")[0].split("|")[-1])
    assert abs(ups_weight_kg - fedex_weight * 0.453592) < 0.05
    assert abs(usps_weight_oz - fedex_weight * 16.0) < 0.5
