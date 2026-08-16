import datetime as dt
import random

from src.ingestion.csv_connector import CSVConnector
from src.ingestion.flat_file_connector import FlatFileConnector
from src.ingestion.registry import build_connector, load_sources
from src.ingestion.sqlite_connector import SQLiteConnector
from src.ingestion.xml_connector import XMLConnector
from src.simulator.product_simulator import generate_product_catalog
from src.simulator.shipping_simulator import generate_shipping_batch
from src.simulator.universe import Universe


def test_load_sources_parses_all_entries():
    sources = load_sources()
    assert "shopify" in sources
    assert sources["shopify"].format == "csv"
    assert sources["products"].incremental_mode == "high_water_mark"
    assert sources["products"].hwm_column == "updated_at"
    assert sources["shipping_usps"].file_pattern == "usps_*.txt"


def test_build_connector_csv(tmp_path):
    sources = load_sources()
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    conn = build_connector(sources["shopify"], f)
    assert isinstance(conn, CSVConnector)


def test_build_connector_sqlite_uses_extra_kwargs(tmp_path):
    universe = Universe(seed=1)
    path = generate_product_catalog(universe, dt.date(2024, 3, 1), tmp_path,
                                     rng=random.Random(1))
    sources = load_sources()
    conn = build_connector(sources["products"], path)
    assert isinstance(conn, SQLiteConnector)
    assert conn.table == "products"
    conn.connect()
    df = conn.extract()
    assert len(df) > 0


def test_build_connector_flat_file_uses_extra_kwargs(tmp_path):
    path = generate_shipping_batch("usps", dt.date(2024, 3, 1), 5, tmp_path,
                                    rng=random.Random(1))
    sources = load_sources()
    conn = build_connector(sources["shipping_usps"], path)
    assert isinstance(conn, FlatFileConnector)
    conn.connect()
    df = conn.extract()
    assert len(df) == 5


def test_build_connector_xml(tmp_path):
    path = generate_shipping_batch("fedex", dt.date(2024, 3, 1), 5, tmp_path,
                                    rng=random.Random(1))
    sources = load_sources()
    conn = build_connector(sources["shipping_fedex"], path)
    assert isinstance(conn, XMLConnector)


def test_build_connector_ups_headerless_csv_uses_columns(tmp_path):
    path = generate_shipping_batch("ups", dt.date(2024, 3, 1), 5, tmp_path,
                                    rng=random.Random(1))
    sources = load_sources()
    conn = build_connector(sources["shipping_ups"], path)
    assert isinstance(conn, CSVConnector)
    conn.connect()
    df = conn.extract()
    assert len(df) == 5
    assert list(df.columns) == ["tracking_number", "reference_order_id", "ship_date",
                                "delivery_date", "status", "weight_kg"]
