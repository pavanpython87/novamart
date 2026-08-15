"""Tracks ingestion state across pipeline runs so re-running the pipeline
is idempotent:
  - file_registry: SHA-256 hash per (source, file_path) — lets file-based
    sources (CSV/Excel/JSON/XML/flat-file) skip files that were already
    ingested and detect files whose content changed since last run.
  - hwm_state: a single high-water-mark value per (source, column) — lets
    query-based sources (SQLite) pull only rows newer than the last run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.ingestion.base_connector import compute_file_hash


class IncrementalTracker:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS file_registry (
                source TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                row_count INTEGER,
                processed_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (source, file_path)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS hwm_state (
                source TEXT NOT NULL,
                hwm_column TEXT NOT NULL,
                hwm_value TEXT,
                updated_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (source, hwm_column)
            )
        """)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- file registry --------------------------------------------------

    def is_new_or_changed(self, source: str, file_path: str | Path) -> bool:
        """True if the file has never been processed for this source, or
        its content hash differs from the last recorded run."""
        current_hash = compute_file_hash(Path(file_path))
        row = self._conn.execute(
            "SELECT file_hash FROM file_registry WHERE source = ? AND file_path = ?",
            (source, str(file_path)),
        ).fetchone()
        return row is None or row[0] != current_hash

    def mark_processed(self, source: str, file_path: str | Path, row_count: int | None = None) -> None:
        file_hash = compute_file_hash(Path(file_path))
        self._conn.execute(
            """INSERT INTO file_registry (source, file_path, file_hash, row_count, processed_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(source, file_path) DO UPDATE SET
                   file_hash = excluded.file_hash,
                   row_count = excluded.row_count,
                   processed_at = excluded.processed_at""",
            (source, str(file_path), file_hash, row_count),
        )
        self._conn.commit()

    # -- high-water-mark --------------------------------------------------

    def get_hwm(self, source: str, hwm_column: str):
        row = self._conn.execute(
            "SELECT hwm_value FROM hwm_state WHERE source = ? AND hwm_column = ?",
            (source, hwm_column),
        ).fetchone()
        return row[0] if row else None

    def set_hwm(self, source: str, hwm_column: str, hwm_value) -> None:
        self._conn.execute(
            """INSERT INTO hwm_state (source, hwm_column, hwm_value, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(source, hwm_column) DO UPDATE SET
                   hwm_value = excluded.hwm_value,
                   updated_at = excluded.updated_at""",
            (source, hwm_column, str(hwm_value)),
        )
        self._conn.commit()
