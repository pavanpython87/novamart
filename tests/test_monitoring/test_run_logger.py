from src.monitoring.run_logger import RunLogger


def test_log_run_appends_jsonl(tmp_path):
    logger = RunLogger(tmp_path / "run_history.jsonl")
    entry = logger.log_run({"mode": "incremental", "order_row_count": 42})

    assert entry["logged_at"]
    assert entry["mode"] == "incremental"

    runs = logger.load_runs()
    assert len(runs) == 1
    assert runs[0]["order_row_count"] == 42


def test_load_runs_limit_and_missing_file(tmp_path):
    logger = RunLogger(tmp_path / "run_history.jsonl")
    logger.log_run({"n": 1})
    logger.log_run({"n": 2})
    logger.log_run({"n": 3})

    assert [r["n"] for r in logger.load_runs(limit=2)] == [2, 3]
    assert logger.last_run()["n"] == 3

    empty = RunLogger(tmp_path / "missing.jsonl")
    assert empty.load_runs() == []
    assert empty.last_run() is None
