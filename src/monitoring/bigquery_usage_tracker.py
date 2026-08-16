"""BigQuery free-tier usage watchdog.

Tracks the two quantities that matter for the free tier (see
PROJECT_PLAN.md 5.7):

  - storage: 10 GB  (summed from table metadata via client.list_tables)
  - query bytes: 1 TB/month (summed from INFORMATION_SCHEMA.JOBS_BY_PROJECT)

The google.cloud.bigquery.Client is injectable so the module is unit
testable without real GCP credentials; tests pass a mock client whose
list_tables/query methods return fake objects.
"""

from __future__ import annotations

import datetime as dt

DEFAULT_DATASET = "novamart"

FREE_TIER_STORAGE_BYTES = 10 * 1024 ** 3   # 10 GB
FREE_TIER_QUERY_BYTES = 1024 ** 4          # 1 TB


class BigQueryUsageTracker:
    def __init__(self, project_id: str, dataset: str = DEFAULT_DATASET, client=None,
                  lookback_days: int = 30):
        self.project_id = project_id
        self.dataset = dataset
        self.client = client
        self.lookback_days = lookback_days

    def check_usage(self) -> dict:
        """Returns current storage + query usage in bytes, alongside each
        free-tier limit and the percentage consumed."""
        storage_bytes = self._storage_bytes()
        query_bytes = self._query_bytes()
        return {
            "storage_bytes": storage_bytes,
            "storage_bytes_limit": FREE_TIER_STORAGE_BYTES,
            "storage_pct": self._pct(storage_bytes, FREE_TIER_STORAGE_BYTES),
            "query_bytes": query_bytes,
            "query_bytes_limit": FREE_TIER_QUERY_BYTES,
            "query_pct": self._pct(query_bytes, FREE_TIER_QUERY_BYTES),
            "checked_at": dt.datetime.now(dt.UTC).isoformat(),
        }

    @staticmethod
    def _pct(used: int, limit: int) -> float:
        return round(used / limit * 100, 4) if limit else 0.0

    def _storage_bytes(self) -> int:
        if self.client is None:
            return 0
        total = 0
        for table in self.client.list_tables(self.dataset):
            total += int(getattr(table, "num_bytes", 0) or 0)
        return total

    def _query_bytes(self) -> int:
        if self.client is None:
            return 0
        sql = (
            "SELECT COALESCE(SUM(total_bytes_billed), 0) AS total "
            "FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
            "WHERE DATE(creation_time) >= DATE_SUB(CURRENT_DATE(), "
            f"INTERVAL {int(self.lookback_days)} DAY)"
        )
        rows = self.client.query(sql).result()
        for row in rows:
            return int(row["total"])
        return 0
