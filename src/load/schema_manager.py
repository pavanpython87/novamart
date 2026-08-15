"""DDL / schema definitions for the DuckDB + BigQuery star schema.

A single source-of-truth column definition per table (using a small
cross-database type vocabulary) is translated into DuckDB CREATE TABLE
DDL and into BigQuery schema field dicts, so the two warehouses never
drift apart. Table names and partition/cluster columns mirror
config/bigquery_schema.yaml.
"""

from __future__ import annotations

DUCKDB_TYPE_MAP = {
    "STRING": "VARCHAR",
    "INTEGER": "BIGINT",
    "FLOAT": "DOUBLE",
    "BOOLEAN": "BOOLEAN",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
}

BIGQUERY_TYPE_MAP = {
    "STRING": "STRING",
    "INTEGER": "INT64",
    "FLOAT": "FLOAT64",
    "BOOLEAN": "BOOL",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
}

TABLE_SCHEMAS: dict[str, dict[str, str]] = {
    "dim_customers": {
        "customer_key": "STRING",
        "first_name": "STRING",
        "last_name": "STRING",
        "email": "STRING",
        "phone": "STRING",
        "postal_code": "STRING",
        "region": "STRING",
        "channels": "STRING",
        "effective_date": "DATE",
        "expiration_date": "DATE",
        "is_current": "BOOLEAN",
    },
    "dim_products": {
        "product_key": "STRING",
        "name": "STRING",
        "category": "STRING",
        "brand": "STRING",
        "unit_cost": "FLOAT",
        "retail_price": "FLOAT",
        "supplier": "STRING",
        "is_active": "BOOLEAN",
    },
    "dim_dates": {
        "date_key": "DATE",
        "year": "INTEGER",
        "quarter": "INTEGER",
        "month": "INTEGER",
        "day": "INTEGER",
        "day_of_week": "INTEGER",
        "is_weekend": "BOOLEAN",
    },
    "dim_channels": {
        "channel_key": "STRING",
        "channel_name": "STRING",
    },
    "fact_orders": {
        "order_id": "STRING",
        "customer_key": "STRING",
        "product_key": "STRING",
        "channel_key": "STRING",
        "date_key": "DATE",
        "quantity": "INTEGER",
        "gross_revenue": "FLOAT",
        "platform_fee": "FLOAT",
        "payment_processing_fee": "FLOAT",
        "returns_and_refunds": "FLOAT",
        "discounts_and_promotions": "FLOAT",
        "net_revenue": "FLOAT",
        "cogs": "FLOAT",
        "gross_profit": "FLOAT",
    },
    "fact_returns": {
        "return_id": "STRING",
        "order_id": "STRING",
        "product_key": "STRING",
        "return_date_key": "DATE",
        "refund_amount": "FLOAT",
        "restocking_fee": "FLOAT",
        "reason_code": "STRING",
    },
    "fact_shipments": {
        "tracking_number": "STRING",
        "order_id": "STRING",
        "carrier": "STRING",
        "ship_date_key": "DATE",
        "delivery_date_key": "DATE",
        "shipping_cost": "FLOAT",
    },
    "fact_inventory_daily": {
        "product_key": "STRING",
        "snapshot_date_key": "DATE",
        "on_hand_qty": "INTEGER",
        "lead_time_days": "INTEGER",
    },
}

PRIMARY_KEYS: dict[str, str] = {
    "dim_customers": "customer_key",
    "dim_products": "product_key",
    "dim_dates": "date_key",
    "dim_channels": "channel_key",
    "fact_orders": "order_id",
    "fact_returns": "return_id",
    "fact_shipments": "tracking_number",
    "fact_inventory_daily": "product_key",
}

SCD2_TABLES = {"dim_customers"}

PARTITION_COLUMNS: dict[str, str | None] = {
    "fact_orders": "date_key",
    "fact_returns": "return_date_key",
    "fact_shipments": "ship_date_key",
    "fact_inventory_daily": "snapshot_date_key",
}

CLUSTER_COLUMNS: dict[str, list[str]] = {
    "fact_orders": ["channel_key", "customer_key"],
    "fact_shipments": ["carrier"],
    "fact_inventory_daily": ["product_key"],
}


def generate_duckdb_ddl(table_name: str) -> str:
    """CREATE TABLE IF NOT EXISTS DDL for a single table, DuckDB dialect."""
    columns = TABLE_SCHEMAS[table_name]
    column_defs = ", ".join(f"{col} {DUCKDB_TYPE_MAP[dtype]}" for col, dtype in columns.items())
    return f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})"


def generate_all_duckdb_ddl() -> dict[str, str]:
    return {table: generate_duckdb_ddl(table) for table in TABLE_SCHEMAS}


def generate_bigquery_schema(table_name: str) -> list[dict[str, str]]:
    """BigQuery schema as a list of {"name", "type", "mode"} dicts, suitable
    for constructing google.cloud.bigquery.SchemaField objects without this
    module needing to import the bigquery client library."""
    columns = TABLE_SCHEMAS[table_name]
    return [
        {"name": col, "type": BIGQUERY_TYPE_MAP[dtype], "mode": "NULLABLE"}
        for col, dtype in columns.items()
    ]
