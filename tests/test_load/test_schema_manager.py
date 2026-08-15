from src.load.schema_manager import (
    PRIMARY_KEYS,
    TABLE_SCHEMAS,
    generate_all_duckdb_ddl,
    generate_bigquery_schema,
    generate_duckdb_ddl,
)


def test_generate_duckdb_ddl_dim_customers():
    ddl = generate_duckdb_ddl("dim_customers")
    assert ddl.startswith("CREATE TABLE IF NOT EXISTS dim_customers (")
    assert "customer_key VARCHAR" in ddl
    assert "is_current BOOLEAN" in ddl


def test_generate_duckdb_ddl_maps_float_to_double():
    ddl = generate_duckdb_ddl("fact_orders")
    assert "net_revenue DOUBLE" in ddl


def test_generate_all_duckdb_ddl_covers_every_table():
    ddls = generate_all_duckdb_ddl()
    assert set(ddls.keys()) == set(TABLE_SCHEMAS.keys())


def test_generate_bigquery_schema_dim_products():
    schema = generate_bigquery_schema("dim_products")
    by_name = {f["name"]: f for f in schema}
    assert by_name["unit_cost"]["type"] == "FLOAT64"
    assert by_name["is_active"]["type"] == "BOOL"
    assert by_name["product_key"]["mode"] == "NULLABLE"


def test_every_table_has_a_primary_key():
    for table in TABLE_SCHEMAS:
        assert table in PRIMARY_KEYS
        assert PRIMARY_KEYS[table] in TABLE_SCHEMAS[table]
