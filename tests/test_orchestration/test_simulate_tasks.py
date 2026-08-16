import datetime as dt

from src.orchestration.tasks.simulate_tasks import simulate_data


def test_simulate_data_writes_files(tmp_path):
    summary = simulate_data.fn(dt.date(2024, 1, 1), dt.date(2024, 1, 1), output_dir=tmp_path, seed=1)
    assert sum(summary.values()) > 0
    assert (tmp_path / "shopify").exists()
