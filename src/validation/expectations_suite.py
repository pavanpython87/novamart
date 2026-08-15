"""Lightweight Great-Expectations-style validation suite, built on
rules_engine.py instead of the actual great-expectations package.

great-expectations pulls in a large, slow-to-import dependency tree for
functionality this project only needs a thin slice of: per-source,
YAML-defined business rules. This suite mirrors the shape callers would
expect from GX (build a suite once per source, call .validate(df) per
batch) without the install/runtime cost.
"""

from __future__ import annotations

import pandas as pd

from src.validation import rules_engine


class ExpectationSuite:
    def __init__(self, source: str, rules: dict | None = None):
        self.source = source
        self.rules = rules if rules is not None else rules_engine.load_rules()

    def validate(self, df: pd.DataFrame) -> dict:
        return rules_engine.evaluate_source(df, self.source, self.rules)
