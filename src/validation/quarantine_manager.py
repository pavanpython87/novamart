"""Routes rows that fail quarantine-level rules to the quarantine SQLite
database (data/quarantine/novamart_quarantine.db per pipeline_config.yaml),
tagging each with the reason codes (rule names) that failed.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_QUARANTINE_DB = Path("data/quarantine/novamart_quarantine.db")


def build_reason_codes(df: pd.DataFrame, validation_result: dict) -> pd.Series:
    """Per-row, comma-joined list of quarantine-rule names that failed."""
    reasons = pd.Series([[] for _ in range(len(df))], index=df.index)
    for rule in validation_result["rule_results"]:
        if rule["skipped"] or rule["on_fail"] != "quarantine":
            continue
        fail_mask = rule["fail_mask"]
        for idx in df.index[fail_mask]:
            reasons.at[idx].append(rule["rule"])
    return reasons.apply(",".join)


def route(df: pd.DataFrame, validation_result: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splits df into (clean_df, quarantined_df). quarantined_df gains a
    reason_codes column; clean_df is returned unchanged."""
    quarantine_mask = validation_result["quarantine_mask"]
    quarantined = df[quarantine_mask].copy()
    if not quarantined.empty:
        quarantined["reason_codes"] = build_reason_codes(df, validation_result)[quarantine_mask]
    clean = df[~quarantine_mask].copy()
    return clean, quarantined


class QuarantineManager:
    def __init__(self, db_path: str | Path = DEFAULT_QUARANTINE_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def persist(self, source: str, quarantined_df: pd.DataFrame, batch_id: str | None = None) -> int:
        """Appends quarantined rows to a per-source table. Returns the
        number of rows written (0 if quarantined_df is empty)."""
        if quarantined_df.empty:
            return 0
        df = quarantined_df.copy()
        df["batch_id"] = batch_id
        df["quarantined_at"] = dt.datetime.now(dt.UTC).isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            table = f"quarantine_{source}"
            df.to_sql(table, conn, if_exists="append", index=False)
            conn.commit()
        finally:
            conn.close()
        return len(df)
