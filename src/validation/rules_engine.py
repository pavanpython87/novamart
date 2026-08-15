"""Rule definitions and evaluation, driven entirely by
config/quality_rules.yaml.

This is the low-level engine; expectations_suite.py wraps it with a
Great-Expectations-style suite API without pulling in the actual (heavy)
great-expectations package.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import yaml

DEFAULT_CONFIG_PATH = Path("config/quality_rules.yaml")

# Longest-prefix-first so ">=" isn't mistaken for ">" while parsing.
ORDERED_OPS = [">=", "<=", "==", ">", "<"]
_BINARY_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def load_rules(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _single_column_mask(df: pd.DataFrame, column: str, condition: str) -> pd.Series:
    """Evaluates a condition like '>= 0' or '<= today' against one column.
    Returns a boolean Series where True means the rule is satisfied."""
    condition = condition.strip()
    if condition == "<= today":
        dates = pd.to_datetime(df[column], errors="coerce")
        return dates <= pd.Timestamp(dt.date.today())

    for op in ORDERED_OPS:
        if condition.startswith(op):
            threshold = float(condition[len(op):].strip())
            values = pd.to_numeric(df[column], errors="coerce")
            return _BINARY_OPS[op](values, threshold)
    raise ValueError(f"Unsupported condition: {condition}")


def _parse_cross_column(condition: str) -> tuple[str, str, str]:
    for op in ORDERED_OPS:
        if op in condition:
            left, right = (part.strip() for part in condition.split(op, 1))
            return left, op, right
    raise ValueError(f"Unsupported condition: {condition}")


def _cross_column_mask(df: pd.DataFrame, condition: str) -> pd.Series:
    """Evaluates a condition like 'delivery_date >= ship_date' comparing two
    columns as dates. Rows where either side is null are treated as
    satisfying the rule (it doesn't apply yet, e.g. not-yet-delivered)."""
    left, op, right = _parse_cross_column(condition)
    left_vals = pd.to_datetime(df[left], errors="coerce")
    right_vals = pd.to_datetime(df[right], errors="coerce")
    return _BINARY_OPS[op](left_vals, right_vals) | left_vals.isna() | right_vals.isna()


def evaluate_source(df: pd.DataFrame, source: str, rules: dict | None = None) -> dict:
    """Evaluates required_columns + business_rules for one source against a
    DataFrame. Returns missing_columns, per-rule pass/fail counts, and
    row-level boolean masks aggregating rules by their on_fail action
    (quarantine vs warn) so callers can route rows accordingly."""
    rules = rules if rules is not None else load_rules()
    source_rules = rules.get(source, {})
    required_columns = source_rules.get("required_columns", [])
    missing_columns = [c for c in required_columns if c not in df.columns]

    rule_results = []
    quarantine_mask = pd.Series(False, index=df.index)
    warn_mask = pd.Series(False, index=df.index)

    for rule in source_rules.get("business_rules", []):
        name = rule["rule"]
        column = rule.get("column")
        condition = rule["condition"]
        on_fail = rule.get("on_fail", "warn")

        columns_needed = [column] if column else list(_parse_cross_column(condition)[::2])
        if any(c not in df.columns for c in columns_needed):
            rule_results.append({"rule": name, "column": column, "on_fail": on_fail,
                                  "pass_count": 0, "fail_count": 0, "skipped": True,
                                  "fail_mask": None})
            continue

        mask = (_single_column_mask(df, column, condition) if column
                else _cross_column_mask(df, condition))
        fail_mask = ~mask.fillna(False)

        rule_results.append({
            "rule": name, "column": column, "on_fail": on_fail,
            "pass_count": int((~fail_mask).sum()), "fail_count": int(fail_mask.sum()),
            "skipped": False, "fail_mask": fail_mask,
        })

        if on_fail == "quarantine":
            quarantine_mask |= fail_mask
        elif on_fail == "warn":
            warn_mask |= fail_mask

    return {
        "source": source,
        "missing_columns": missing_columns,
        "rule_results": rule_results,
        "quarantine_mask": quarantine_mask,
        "warn_mask": warn_mask,
    }
