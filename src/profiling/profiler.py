"""Lightweight, dependency-free data profiler.

Computes row/column counts and per-column null rates, dtypes, and value
distribution summaries (numeric describe()-style stats, or top category
frequencies). Deliberately avoids the heavy ydata-profiling dependency for
fast iteration; its output feeds both the quality gate (baseline_manager
deltas) and later statistical drift checks (drift_detector).
"""

from __future__ import annotations

import pandas as pd

NUMERIC_KINDS = "iuf"  # int, unsigned int, float


def _column_profile(series: pd.Series) -> dict:
    total = len(series)
    null_count = int(series.isna().sum())
    profile = {
        "dtype": str(series.dtype),
        "null_count": null_count,
        "null_pct": round(null_count / total * 100, 2) if total else 0.0,
        "distinct_count": int(series.nunique(dropna=True)),
    }

    non_null = series.dropna()
    if non_null.empty:
        return profile

    if series.dtype.kind in NUMERIC_KINDS:
        profile["numeric_summary"] = {
            "min": float(non_null.min()),
            "max": float(non_null.max()),
            "mean": float(non_null.mean()),
            "std": float(non_null.std()) if len(non_null) > 1 else 0.0,
        }
    else:
        profile["top_values"] = non_null.astype(str).value_counts().head(10).to_dict()

    return profile


def profile_dataframe(df: pd.DataFrame, source_name: str) -> dict:
    return {
        "source": source_name,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": {col: _column_profile(df[col]) for col in df.columns},
    }
