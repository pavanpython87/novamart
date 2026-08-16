"""Validation + quarantine-routing task: evaluates a source's business
rules and required columns, splits the batch into clean/quarantined rows,
and persists the quarantined rows for later review.
"""

from __future__ import annotations

import pandas as pd
from prefect import task

from src.validation.quarantine_manager import QuarantineManager, route
from src.validation.rules_engine import evaluate_source


@task(name="validate-and-quarantine")
def validate_and_quarantine(
    df: pd.DataFrame, source_name: str, quarantine_manager: QuarantineManager,
    batch_id: str | None = None,
) -> dict:
    """Returns {"clean_df", "quarantined_df", "validation_result"}."""
    validation_result = evaluate_source(df, source_name)
    clean_df, quarantined_df = route(df, validation_result)
    if not quarantined_df.empty:
        quarantine_manager.persist(source_name, quarantined_df, batch_id=batch_id)
    return {
        "clean_df": clean_df,
        "quarantined_df": quarantined_df,
        "validation_result": validation_result,
    }
