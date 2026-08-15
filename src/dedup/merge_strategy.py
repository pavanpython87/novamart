"""Builds a "golden record" from a cluster of matched records (customer
duplicates across channels, or order duplicates from re-uploaded files):
for each field, picks the most complete (non-null) value, with the most
recently updated record winning ties.
"""

from __future__ import annotations

import pandas as pd


def build_golden_record(records: list[dict], timestamp_field: str = "updated_at") -> dict:
    if not records:
        raise ValueError("records must be non-empty")

    def sort_key(r: dict):
        ts = r.get(timestamp_field)
        return pd.to_datetime(ts) if ts else pd.Timestamp.min

    ordered = sorted(records, key=sort_key, reverse=True)  # most recent first

    all_fields = {k for r in records for k in r}
    golden: dict = {}
    for field_name in all_fields:
        golden[field_name] = next(
            (r[field_name] for r in ordered if r.get(field_name) not in (None, "")),
            None,
        )
    return golden
