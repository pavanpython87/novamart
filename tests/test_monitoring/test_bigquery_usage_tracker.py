from src.monitoring.bigquery_usage_tracker import (
    FREE_TIER_QUERY_BYTES,
    FREE_TIER_STORAGE_BYTES,
    BigQueryUsageTracker,
)


class _FakeTable:
    def __init__(self, num_bytes):
        self.num_bytes = num_bytes


class _FakeJob:
    def __init__(self, total):
        self._total = total

    def result(self):
        return [{"total": self._total}]


class _FakeClient:
    def __init__(self, storage_tables, query_total):
        self._tables = storage_tables
        self._total = query_total

    def list_tables(self, dataset):
        assert dataset == "novamart"
        return self._tables

    def query(self, sql):
        assert "INFORMATION_SCHEMA.JOBS_BY_PROJECT" in sql
        return _FakeJob(self._total)


def test_check_usage_sums_storage_and_query_bytes():
    client = _FakeClient([_FakeTable(100), _FakeTable(50)], 12345)
    tracker = BigQueryUsageTracker("my-project", client=client)

    usage = tracker.check_usage()

    assert usage["storage_bytes"] == 150
    assert usage["query_bytes"] == 12345
    assert usage["storage_bytes_limit"] == FREE_TIER_STORAGE_BYTES
    assert usage["query_bytes_limit"] == FREE_TIER_QUERY_BYTES
    assert 0 <= usage["storage_pct"] < 100
    assert 0 <= usage["query_pct"] < 100


def test_check_usage_without_client_returns_zero():
    tracker = BigQueryUsageTracker("my-project")
    usage = tracker.check_usage()

    assert usage["storage_bytes"] == 0
    assert usage["query_bytes"] == 0
    assert usage["storage_pct"] == 0.0
    assert usage["query_pct"] == 0.0
