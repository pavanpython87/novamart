"""SQLite connector: table/query-based extraction with optional
high-water-mark (HWM) filtering for incremental loads.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.ingestion.base_connector import BaseConnector


class SQLiteConnector(BaseConnector):
    def __init__(self, source_path, table: str | None = None, query: str | None = None,
                 hwm_column: str | None = None, hwm_value=None):
        if not table and not query:
            raise ValueError("Either table or query must be provided")
        super().__init__(source_path)
        self.table = table
        self.query = query
        self.hwm_column = hwm_column
        self.hwm_value = hwm_value
        self.max_hwm_value = None

    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        self._connected = True

    def extract(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.source_path)
        try:
            sql, params = self._build_query()
            df = pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

        if self.hwm_column and self.hwm_column in df.columns and not df.empty:
            self.max_hwm_value = df[self.hwm_column].max()
        return df

    def _build_query(self) -> tuple[str, list]:
        if self.query:
            sql = self.query
            params: list = []
        else:
            sql = f"SELECT * FROM {self.table}"  # table name is caller-controlled config, not user input
            params = []
            if self.hwm_column and self.hwm_value is not None:
                sql += f" WHERE {self.hwm_column} > ?"
                params.append(self.hwm_value)
        return sql, params
