from src.ingestion.csv_connector import CSVConnector, detect_dialect, detect_encoding


def test_detect_encoding_utf8_sig_bom():
    raw = "name\nJosé\n".encode("utf-8-sig")
    assert detect_encoding(raw) == "utf-8-sig"


def test_detect_encoding_plain_utf8():
    raw = b"name\nBob\n"
    assert detect_encoding(raw) == "utf-8-sig" or detect_encoding(raw) == "utf-8"


def test_detect_dialect_comma():
    dialect = detect_dialect("a,b,c\n1,2,3\n4,5,6")
    assert dialect.delimiter == ","


def test_detect_dialect_semicolon():
    dialect = detect_dialect("a;b;c\n1;2;3\n4;5;6\n7;8;9")
    assert dialect.delimiter == ";"


def test_csv_connector_reads_bom_file(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_bytes("name,city\nJosé,München\n".encode("utf-8-sig"))
    conn = CSVConnector(f)
    conn.connect()
    df = conn.extract()
    assert conn.encoding == "utf-8-sig"
    assert list(df.columns) == ["name", "city"]
    assert df.iloc[0]["name"] == "José"


def test_csv_connector_skips_blank_rows(tmp_path):
    f = tmp_path / "blanks.csv"
    f.write_text("a,b\n1,2\n\n3,4\n\n\n5,6\n")
    conn = CSVConnector(f)
    conn.connect()
    df = conn.extract()
    assert len(df) == 3


def test_csv_connector_missing_file_raises(tmp_path):
    conn = CSVConnector(tmp_path / "nope.csv")
    import pytest
    with pytest.raises(FileNotFoundError):
        conn.connect()


def test_csv_connector_full_run_metadata(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n3,4\n")
    result = CSVConnector(f).run()
    assert result.metadata["row_count"] == 2
    assert list(result.data.columns) == ["a", "b"]
