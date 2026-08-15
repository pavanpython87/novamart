"""Abstract base for all format-specific ingestion connectors.

Every connector turns one source file into a pandas DataFrame (or, for
multi-sheet Excel, a dict of DataFrames) plus a metadata envelope
(row_count, file_hash, schema_fingerprint, extraction_timestamp) as
described in the project plan's ingestion layer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class ExtractionResult:
    data: pd.DataFrame | dict[str, pd.DataFrame]
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schema_fingerprint(df: pd.DataFrame) -> str:
    return ",".join(f"{col}:{dtype}" for col, dtype in df.dtypes.astype(str).items())


class BaseConnector(ABC):
    """Subclasses implement `connect()` and `extract()`. `run()` ties them
    together and attaches the standard metadata envelope."""

    def __init__(self, source_path: str | Path):
        self.source_path = Path(source_path)
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Validate the source is readable (file exists, right format, etc.)."""

    @abstractmethod
    def extract(self) -> pd.DataFrame | dict[str, pd.DataFrame]:
        """Return the extracted data as a DataFrame, or a dict of DataFrames
        keyed by sheet/table name for multi-relation sources."""

    def get_metadata(self, data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, Any]:
        if isinstance(data, dict):
            row_count = sum(len(df) for df in data.values())
            fingerprint = {name: schema_fingerprint(df) for name, df in data.items()}
        else:
            row_count = len(data)
            fingerprint = schema_fingerprint(data)

        return {
            "source_file": str(self.source_path),
            "file_hash": compute_file_hash(self.source_path),
            "file_size_bytes": self.source_path.stat().st_size,
            "row_count": row_count,
            "schema_fingerprint": fingerprint,
            "extraction_timestamp": dt.datetime.now(dt.UTC).isoformat(),
        }

    def run(self) -> ExtractionResult:
        self.connect()
        data = self.extract()
        metadata = self.get_metadata(data)
        return ExtractionResult(data=data, metadata=metadata)
