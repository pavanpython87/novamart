import datetime as dt
import random

from src.ingestion.xml_connector import XMLConnector
from src.simulator.shipping_simulator import generate_shipping_batch


def test_xml_connector_reads_namespaced_fedex_feed(tmp_path):
    path = generate_shipping_batch("fedex", dt.date(2024, 3, 1), 12, tmp_path,
                                    rng=random.Random(1))
    conn = XMLConnector(path)
    conn.connect()
    df = conn.extract()
    assert len(df) == 12
    assert conn.namespace == "http://fedex.com/ship"
    assert "TrackingNumber" in df.columns
    assert "Status" in df.columns


def test_xml_connector_missing_file_raises(tmp_path):
    conn = XMLConnector(tmp_path / "nope.xml")
    import pytest
    with pytest.raises(FileNotFoundError):
        conn.connect()


def test_xml_connector_full_run_metadata(tmp_path):
    path = generate_shipping_batch("fedex", dt.date(2024, 3, 1), 5, tmp_path,
                                    rng=random.Random(2))
    result = XMLConnector(path).run()
    assert result.metadata["row_count"] == 5
