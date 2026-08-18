from unittest.mock import MagicMock

import pandas as pd

from src.load.bigquery_loader import BigQueryLoader


def _make_loader():
    client = MagicMock()
    client.create_table.side_effect = lambda table, exists_ok=True: table
    loader = BigQueryLoader(project_id="proj", dataset="novamart", client=client)
    return loader, client


def test_ensure_dataset_calls_client():
    loader, client = _make_loader()
    loader.ensure_dataset()
    assert client.create_dataset.called
    _, kwargs = client.create_dataset.call_args
    assert kwargs["exists_ok"] is True


def test_ensure_table_sets_partitioning_and_clustering():
    loader, client = _make_loader()
    table = loader.ensure_table("fact_orders")
    assert table.time_partitioning.field == "date_key"
    assert table.clustering_fields == ["channel_key", "customer_key"]
    assert client.create_table.called


def test_ensure_table_dimension_table_has_no_partitioning():
    loader, client = _make_loader()
    table = loader.ensure_table("dim_products")
    assert table.time_partitioning is None
    assert table.clustering_fields is None


def test_read_dataframe_queries_full_table():
    loader, client = _make_loader()
    expected = pd.DataFrame([{"order_id": "O1"}])
    client.query.return_value.to_dataframe.return_value = expected

    result = loader.read_dataframe("stg_orders")

    assert client.query.called
    sql = client.query.call_args[0][0]
    assert "SELECT * FROM `proj.novamart.stg_orders`" in sql
    pd.testing.assert_frame_equal(result, expected)


def test_read_dataframe_returns_empty_df_on_query_failure():
    loader, client = _make_loader()
    client.query.side_effect = Exception("table not found")

    result = loader.read_dataframe("stg_orders")

    assert result.empty


def test_load_dataframe_runs_load_job_and_waits_for_result():
    loader, client = _make_loader()
    mock_job = MagicMock()
    client.load_table_from_dataframe.return_value = mock_job

    df = pd.DataFrame([{"order_id": "O1"}])
    loader.load_dataframe("fact_orders", df)

    assert client.load_table_from_dataframe.called
    args, _ = client.load_table_from_dataframe.call_args
    assert args[1] == "proj.novamart.fact_orders"
    assert mock_job.result.called


def test_upsert_empty_dataframe_is_noop():
    loader, client = _make_loader()
    loader.upsert("fact_orders", pd.DataFrame(columns=["order_id"]))
    assert not client.load_table_from_dataframe.called
    assert not client.query.called


def test_upsert_stages_then_merges():
    loader, client = _make_loader()
    client.load_table_from_dataframe.return_value = MagicMock()
    client.query.return_value = MagicMock()

    df = pd.DataFrame([{"order_id": "O1", "customer_key": "C1"}])
    loader.upsert("fact_orders", df)

    assert client.load_table_from_dataframe.called
    load_args, _ = client.load_table_from_dataframe.call_args
    assert load_args[1] == "proj.novamart._stg_fact_orders"

    assert client.query.called
    sql = client.query.call_args[0][0]
    assert "MERGE `proj.novamart.fact_orders`" in sql
    assert "ON target.order_id = source.order_id" in sql
    assert "WHEN MATCHED THEN UPDATE SET" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql
