"""Deduplicates orders via a composite key, optionally constrained to a
time window. Handles the "same file uploaded twice" scenario (timeline.py's
duplicate_upload_window, historical months 10-11) where re-uploaded rows
are identical except perhaps a slightly different extraction timestamp.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_KEY_COLUMNS = ["order_id"]


def deduplicate_orders(df: pd.DataFrame, key_columns: list[str] | None = None,
                        keep: str = "first") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splits df into (deduped_df, duplicates_df) based on an exact match
    on key_columns."""
    key_columns = key_columns or DEFAULT_KEY_COLUMNS
    is_dup = df.duplicated(subset=key_columns, keep=keep)
    return df[~is_dup].copy(), df[is_dup].copy()


def deduplicate_within_time_window(df: pd.DataFrame, key_columns: list[str],
                                    timestamp_column: str,
                                    window_minutes: int = 60) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Like deduplicate_orders, but two rows sharing the same key are only
    considered duplicates if their timestamps fall within window_minutes of
    each other — guards against legitimate repeat orders (same customer,
    same SKU) placed far apart in time."""
    working = df.copy()
    working["_ts"] = pd.to_datetime(working[timestamp_column], errors="coerce")
    ordered = working.sort_values("_ts")

    keep_mask = pd.Series(True, index=ordered.index)
    last_seen: dict[tuple, pd.Timestamp] = {}
    for idx, row in ordered.iterrows():
        key = tuple(row[c] for c in key_columns)
        ts = row["_ts"]
        prev_ts = last_seen.get(key)
        if (prev_ts is not None and pd.notna(ts) and pd.notna(prev_ts)
                and abs((ts - prev_ts).total_seconds()) <= window_minutes * 60):
            keep_mask.at[idx] = False
        else:
            last_seen[key] = ts

    keep_index = df.index.intersection(keep_mask[keep_mask].index)
    dup_index = df.index.intersection(keep_mask[~keep_mask].index)
    return df.loc[keep_index].sort_index(), df.loc[dup_index].sort_index()
