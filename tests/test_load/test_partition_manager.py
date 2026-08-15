import datetime as dt

import pytest

from src.load.partition_manager import (
    build_delete_partition_sql,
    build_partition_decorator,
    build_partition_filter,
    expiration_timestamp_ms,
    get_partition_column,
)


def test_get_partition_column():
    assert get_partition_column("fact_orders") == "date_key"
    assert get_partition_column("dim_customers") is None


def test_build_partition_filter():
    sql = build_partition_filter("fact_orders", dt.date(2024, 1, 1), dt.date(2024, 1, 31))
    assert sql == "date_key BETWEEN DATE('2024-01-01') AND DATE('2024-01-31')"


def test_build_partition_filter_unpartitioned_table_raises():
    with pytest.raises(ValueError):
        build_partition_filter("dim_customers", dt.date(2024, 1, 1), dt.date(2024, 1, 31))


def test_build_partition_decorator():
    decorator = build_partition_decorator("fact_orders", dt.date(2024, 3, 5))
    assert decorator == "fact_orders$20240305"


def test_build_delete_partition_sql():
    sql = build_delete_partition_sql("proj", "novamart", "fact_shipments", dt.date(2024, 3, 5))
    assert sql == (
        "DELETE FROM `proj.novamart.fact_shipments` WHERE ship_date_key = DATE('2024-03-05')"
    )


def test_expiration_timestamp_ms_is_after_as_of():
    as_of = dt.date(2024, 1, 1)
    ts = expiration_timestamp_ms(retention_days=30, as_of=as_of)
    expected = int(dt.datetime(2024, 1, 31).timestamp() * 1000)
    assert ts == expected
