"""Date-based partition management helpers for BigQuery fact tables.

Pure functions only (no BigQuery client dependency) so partition logic
can be unit tested without network access; bigquery_loader.py calls
these to build the SQL/decorators it sends to the client.
"""

from __future__ import annotations

import datetime as dt

from src.load.schema_manager import PARTITION_COLUMNS


def get_partition_column(table_name: str) -> str | None:
    return PARTITION_COLUMNS.get(table_name)


def _require_partition_column(table_name: str) -> str:
    column = PARTITION_COLUMNS.get(table_name)
    if not column:
        raise ValueError(f"{table_name} is not a partitioned table")
    return column


def build_partition_filter(table_name: str, start_date: dt.date, end_date: dt.date) -> str:
    """SQL WHERE-clause fragment restricting a query to a date range on the
    table's partition column, for partition pruning during backfills."""
    column = _require_partition_column(table_name)
    return f"{column} BETWEEN DATE('{start_date.isoformat()}') AND DATE('{end_date.isoformat()}')"


def build_partition_decorator(table_name: str, date: dt.date) -> str:
    """BigQuery partition decorator (table$YYYYMMDD) for targeting a single
    day's partition directly, e.g. for a delete+reload backfill."""
    _require_partition_column(table_name)
    return f"{table_name}${date.strftime('%Y%m%d')}"


def build_delete_partition_sql(project_id: str, dataset: str, table_name: str, date: dt.date) -> str:
    column = _require_partition_column(table_name)
    return (
        f"DELETE FROM `{project_id}.{dataset}.{table_name}` "
        f"WHERE {column} = DATE('{date.isoformat()}')"
    )


def expiration_timestamp_ms(retention_days: int, as_of: dt.date | None = None) -> int:
    """Millisecond epoch timestamp `retention_days` after `as_of` (or
    today), for setting a table/partition expiration policy."""
    as_of = as_of or dt.date.today()
    expiry = dt.datetime.combine(as_of + dt.timedelta(days=retention_days), dt.time.min)
    return int(expiry.timestamp() * 1000)
