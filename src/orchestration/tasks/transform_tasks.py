"""Business-logic transformation tasks: maps cleaned/deduped per-source
data into the canonical order-line shape the transform layer expects
(see src.transform.revenue_calculator's module docstring for the field
list), then computes revenue/profit economics and customer analytics.

Each source's cleaned column names differ, so callers supply a field_map
(canonical_field -> source_column) rather than this module guessing
column names.
"""

from __future__ import annotations

import pandas as pd
from prefect import task

from src.transform.customer_analytics import build_customer_analytics
from src.transform.revenue_calculator import calculate_order_economics_batch


def map_to_canonical_orders(
    df: pd.DataFrame, channel: str, field_map: dict[str, str], defaults: dict | None = None,
) -> pd.DataFrame:
    """Renames df's columns per field_map (canonical_field -> source_column)
    into the canonical order-line shape, filling any canonical field not
    present in field_map/df from `defaults`."""
    if df.empty:
        return pd.DataFrame(columns=[*field_map.keys(), "channel"])

    defaults = defaults or {}
    result = pd.DataFrame(index=df.index)
    for canonical_field, source_column in field_map.items():
        if source_column in df.columns:
            result[canonical_field] = df[source_column]
        else:
            result[canonical_field] = defaults.get(canonical_field)
    result["channel"] = channel
    return result


@task(name="calculate-order-economics")
def calculate_order_economics(orders: pd.DataFrame) -> pd.DataFrame:
    return calculate_order_economics_batch(orders)


@task(name="build-customer-analytics")
def build_analytics(orders: pd.DataFrame) -> pd.DataFrame:
    return build_customer_analytics(orders)
