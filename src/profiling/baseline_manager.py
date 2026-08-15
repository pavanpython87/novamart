"""Persists per-source statistical baselines (profiler.py output) between
pipeline runs, and computes deltas between a fresh batch profile and the
stored baseline for the quality gate to act on.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_BASELINE_DIR = Path("data/profiling_reports/baselines")


class BaselineManager:
    def __init__(self, baseline_dir: str | Path = DEFAULT_BASELINE_DIR):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, source: str) -> Path:
        return self.baseline_dir / f"{source}.json"

    def load(self, source: str) -> dict | None:
        path = self._path_for(source)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, source: str, profile: dict) -> None:
        with open(self._path_for(source), "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

    def compute_delta(self, current: dict, baseline: dict) -> dict:
        prev_rows = baseline["row_count"]
        row_count_pct_change = (
            round((current["row_count"] - prev_rows) / prev_rows * 100, 2)
            if prev_rows else None
        )

        current_cols = set(current["columns"])
        baseline_cols = set(baseline["columns"])
        new_columns = sorted(current_cols - baseline_cols)
        missing_columns = sorted(baseline_cols - current_cols)

        null_pct_deltas = {}
        dtype_changes = {}
        for col in current_cols & baseline_cols:
            cur_col = current["columns"][col]
            base_col = baseline["columns"][col]
            null_pct_deltas[col] = round(cur_col["null_pct"] - base_col["null_pct"], 2)
            if cur_col["dtype"] != base_col["dtype"]:
                dtype_changes[col] = {"from": base_col["dtype"], "to": cur_col["dtype"]}

        return {
            "row_count_delta": current["row_count"] - prev_rows,
            "row_count_pct_change": row_count_pct_change,
            "new_columns": new_columns,
            "missing_columns": missing_columns,
            "null_pct_deltas": null_pct_deltas,
            "dtype_changes": dtype_changes,
        }
