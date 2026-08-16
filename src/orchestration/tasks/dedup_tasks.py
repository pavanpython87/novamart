"""Deduplication + entity resolution tasks: cross-channel customer
matching and within-source order deduplication.
"""

from __future__ import annotations

import pandas as pd
from prefect import task

from src.dedup.customer_resolver import find_candidate_matches
from src.dedup.order_deduplicator import deduplicate_orders


@task(name="resolve-customers")
def resolve_customers(records: pd.DataFrame) -> list[dict]:
    """Finds cross-channel customer match candidates. Auto-merge/review
    routing is left to the caller (see match["action"])."""
    return find_candidate_matches(records)


@task(name="dedup-orders")
def dedup_orders(df: pd.DataFrame, key_columns: list[str] | None = None) -> dict:
    """Returns {"deduped_df", "duplicates_df"}."""
    deduped, duplicates = deduplicate_orders(df, key_columns=key_columns)
    return {"deduped_df": deduped, "duplicates_df": duplicates}
