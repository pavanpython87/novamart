import datetime as dt
import random

import pytest

from src.ingestion.flat_file_connector import FlatFileConnector
from src.simulator.shipping_simulator import generate_shipping_batch

USPS_COLUMNS = ["tracking_number", "reference_order_id", "ship_date", "delivery_date",
                 "status", "weight_oz"]


def test_flat_file_connector_parses_pipe_delimited(tmp_path):
    path = generate_shipping_batch("usps", dt.date(2024, 3, 1), 10, tmp_path,
                                    rng=random.Random(1))
    conn = FlatFileConnector(path, columns=USPS_COLUMNS, delimiter="|")
    conn.connect()
    df = conn.extract()
    assert len(df) == 10
    assert list(df.columns) == USPS_COLUMNS


def test_flat_file_connector_missing_file_raises(tmp_path):
    conn = FlatFileConnector(tmp_path / "nope.txt", columns=USPS_COLUMNS)
    with pytest.raises(FileNotFoundError):
        conn.connect()


def test_flat_file_connector_skips_blank_lines(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("a|1\n\nb|2\n\n")
    conn = FlatFileConnector(path, columns=["name", "value"], delimiter="|")
    conn.connect()
    df = conn.extract()
    assert len(df) == 2
