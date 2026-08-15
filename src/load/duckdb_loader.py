"""Local DuckDB warehouse loader: schema creation + upsert logic, with
SCD Type 2 handling for the dim_customers table.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd

from src.load.schema_manager import PRIMARY_KEYS, generate_all_duckdb_ddl


class DuckDBLoader:
    def __init__(self, db_path: str = ":memory:"):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)

    def create_schema(self) -> None:
        for ddl in generate_all_duckdb_ddl().values():
            self.conn.execute(ddl)

    def close(self) -> None:
        self.conn.close()

    def upsert(self, table_name: str, df: pd.DataFrame) -> None:
        """Delete-then-insert upsert keyed on the table's primary key:
        idempotent for reprocessing the same batch twice.

        df's columns must match the target table's schema, in the same
        order (see schema_manager.TABLE_SCHEMAS), since DuckDB's
        ``INSERT INTO ... SELECT *`` matches columns positionally."""
        if df.empty:
            return
        pk = PRIMARY_KEYS[table_name]
        keys = df[pk].tolist()
        placeholders = ", ".join(["?"] * len(keys))
        self.conn.execute(f"DELETE FROM {table_name} WHERE {pk} IN ({placeholders})", keys)
        self.conn.register("_incoming_df", df)
        self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM _incoming_df")
        self.conn.unregister("_incoming_df")

    def upsert_scd2_customers(self, incoming_df: pd.DataFrame, as_of: dt.date | None = None) -> None:
        """SCD Type 2 upsert for dim_customers: expires the current row for
        any customer whose tracked attributes changed, and inserts a new
        current row. New customers are inserted directly."""
        if incoming_df.empty:
            return
        as_of = as_of or dt.date.today()
        tracked_cols = [c for c in incoming_df.columns if c not in ("effective_date", "expiration_date", "is_current")]

        current_rows = self.conn.execute(
            "SELECT * FROM dim_customers WHERE is_current = TRUE"
        ).fetchdf()
        current_by_key = {row["customer_key"]: row for _, row in current_rows.iterrows()} if not current_rows.empty else {}

        to_expire: list[str] = []
        to_insert: list[dict] = []

        for _, incoming in incoming_df.iterrows():
            key = incoming["customer_key"]
            existing = current_by_key.get(key)
            if existing is None:
                to_insert.append(self._new_scd2_row(incoming, tracked_cols, as_of))
                continue
            changed = any(existing.get(c) != incoming.get(c) for c in tracked_cols)
            if changed:
                to_expire.append(key)
                to_insert.append(self._new_scd2_row(incoming, tracked_cols, as_of))

        if to_expire:
            placeholders = ", ".join(["?"] * len(to_expire))
            self.conn.execute(
                f"UPDATE dim_customers SET expiration_date = ?, is_current = FALSE "
                f"WHERE customer_key IN ({placeholders}) AND is_current = TRUE",
                [as_of, *to_expire],
            )

        if to_insert:
            insert_df = pd.DataFrame(to_insert)
            self.conn.register("_scd2_incoming", insert_df)
            self.conn.execute("INSERT INTO dim_customers SELECT * FROM _scd2_incoming")
            self.conn.unregister("_scd2_incoming")

    @staticmethod
    def _new_scd2_row(incoming: pd.Series, tracked_cols: list[str], as_of: dt.date) -> dict:
        row = {c: incoming.get(c) for c in tracked_cols}
        row["effective_date"] = as_of
        row["expiration_date"] = None
        row["is_current"] = True
        return row
