from pathlib import Path

from src.ingestion.incremental_tracker import IncrementalTracker
from src.ingestion.registry import SourceConfig
from src.orchestration.tasks.ingest_tasks import ingest_source


def _write_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("order_id,total\n" + "\n".join(rows), encoding="utf-8")


def test_ingest_source_file_registry_ingests_new_files(tmp_path):
    incoming = tmp_path / "incoming" / "shopify"
    _write_csv(incoming / "batch1.csv", ["O1,10.0", "O2,20.0"])

    source = SourceConfig(name="shopify", format="csv", incoming_dir=incoming, incremental_mode="file_registry")
    tracker = IncrementalTracker(tmp_path / "tracker.db")

    df = ingest_source.fn(source, tracker)
    assert len(df) == 2
    tracker.close()


def test_ingest_source_file_registry_is_idempotent(tmp_path):
    incoming = tmp_path / "incoming" / "shopify"
    _write_csv(incoming / "batch1.csv", ["O1,10.0"])

    source = SourceConfig(name="shopify", format="csv", incoming_dir=incoming, incremental_mode="file_registry")
    tracker = IncrementalTracker(tmp_path / "tracker.db")

    first = ingest_source.fn(source, tracker)
    second = ingest_source.fn(source, tracker)
    assert len(first) == 1
    assert second.empty
    tracker.close()


def test_ingest_source_no_files_returns_empty(tmp_path):
    incoming = tmp_path / "incoming" / "shopify"
    incoming.mkdir(parents=True)
    source = SourceConfig(name="shopify", format="csv", incoming_dir=incoming, incremental_mode="file_registry")
    tracker = IncrementalTracker(tmp_path / "tracker.db")

    df = ingest_source.fn(source, tracker)
    assert df.empty
    tracker.close()


def test_ingest_source_file_registry_skips_corrupt_file(tmp_path):
    incoming = tmp_path / "incoming" / "shopify"
    _write_csv(incoming / "good1.csv", ["O1,10.0", "O2,20.0"])
    (incoming / "corrupt.csv").write_text("", encoding="utf-8")  # chaos: emptied file
    _write_csv(incoming / "good2.csv", ["O3,30.0"])

    source = SourceConfig(name="shopify", format="csv", incoming_dir=incoming, incremental_mode="file_registry")
    tracker = IncrementalTracker(tmp_path / "tracker.db")

    df = ingest_source.fn(source, tracker)

    # Both good files are still ingested despite the corrupt one in between.
    assert len(df) == 3
    tracker.close()


def test_ingest_source_hwm_mode(tmp_path):
    import sqlite3

    incoming = tmp_path / "incoming" / "products"
    incoming.mkdir(parents=True)
    db_path = incoming / "products.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE products (product_id TEXT, updated_at TEXT)")
    conn.executemany("INSERT INTO products VALUES (?, ?)", [
        ("P1", "2024-01-01"), ("P2", "2024-01-02"),
    ])
    conn.commit()
    conn.close()

    source = SourceConfig(name="products", format="sqlite", incoming_dir=incoming, incremental_mode="high_water_mark", hwm_column="updated_at")
    tracker = IncrementalTracker(tmp_path / "tracker.db")

    df = ingest_source.fn(source, tracker)
    assert len(df) == 2
    assert tracker.get_hwm("products", "updated_at") == "2024-01-02"
    tracker.close()
