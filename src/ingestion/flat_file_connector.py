"""Flat-file connector: headerless delimited text (e.g. the USPS pipe-
delimited shipping feed) parsed against a caller-supplied column list.
"""

from __future__ import annotations

import pandas as pd

from src.ingestion.base_connector import BaseConnector


class FlatFileConnector(BaseConnector):
    def __init__(self, source_path, columns: list[str], delimiter: str = "|",
                 encoding: str = "utf-8"):
        super().__init__(source_path)
        self.columns = columns
        self.delimiter = delimiter
        self.encoding = encoding

    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        self._connected = True

    def extract(self) -> pd.DataFrame:
        text = self.source_path.read_text(encoding=self.encoding)
        rows = [line.split(self.delimiter) for line in text.splitlines() if line.strip() != ""]
        return pd.DataFrame(rows, columns=self.columns)
