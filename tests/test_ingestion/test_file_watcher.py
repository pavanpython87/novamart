from src.ingestion.file_watcher import scan_incoming


def test_scan_incoming_returns_matching_files_sorted(tmp_path):
    (tmp_path / "b.csv").write_text("x")
    (tmp_path / "a.csv").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    files = scan_incoming(tmp_path, "*.csv")
    assert [f.name for f in files] == ["a.csv", "b.csv"]


def test_scan_incoming_skips_hidden_files(tmp_path):
    (tmp_path / ".gitkeep").write_text("")
    (tmp_path / "data.csv").write_text("x")
    files = scan_incoming(tmp_path, "*")
    assert [f.name for f in files] == ["data.csv"]


def test_scan_incoming_missing_dir_returns_empty(tmp_path):
    assert scan_incoming(tmp_path / "does_not_exist") == []


def test_scan_incoming_default_pattern_matches_all(tmp_path):
    (tmp_path / "a.xml").write_text("x")
    (tmp_path / "b.csv").write_text("x")
    files = scan_incoming(tmp_path)
    assert len(files) == 2
