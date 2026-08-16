"""Cleaning/standardization task: applies the cleaning-layer's per-field
normalizers (phone, date, currency, name, unit, status) to whichever
columns of a batch need them.

There's no single fixed schema across sources, so callers pass a
column -> normalizer mapping describing which columns of *their* source
need which transformation; this task just applies that mapping uniformly.
See CLEANERS for the available normalizer functions.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from prefect import task

from src.cleaning.currency_cleaner import clean_currency
from src.cleaning.date_normalizer import normalize_date
from src.cleaning.name_normalizer import normalize_name
from src.cleaning.phone_normalizer import normalize_phone
from src.cleaning.status_harmonizer import harmonize_order_status, harmonize_shipment_status

CLEANERS: dict[str, Callable] = {
    "phone": normalize_phone,
    "date": normalize_date,
    "currency": clean_currency,
    "name": normalize_name,
    "order_status": harmonize_order_status,
    "shipment_status": harmonize_shipment_status,
}


@task(name="clean-source")
def clean_source(df: pd.DataFrame, column_normalizers: dict[str, str]) -> pd.DataFrame:
    """column_normalizers maps column name -> normalizer key (one of
    CLEANERS). Unknown columns/keys are ignored so callers can pass a
    superset mapping shared across sources without per-source branching."""
    if df.empty:
        return df

    result = df.copy()
    for column, normalizer_key in column_normalizers.items():
        if column not in result.columns or normalizer_key not in CLEANERS:
            continue
        cleaner = CLEANERS[normalizer_key]
        result[column] = result[column].apply(cleaner)
    return result
