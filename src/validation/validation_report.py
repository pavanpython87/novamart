"""Builds a per-batch validation summary from rules_engine's output:
pass/fail counts per rule, quarantine/warn totals, and missing columns.
JSON-safe (no pandas objects), suitable for logging or persisting alongside
profiling reports.
"""

from __future__ import annotations


def build_report(validation_result: dict, row_count: int) -> dict:
    rule_breakdown = [
        {
            "rule": r["rule"],
            "column": r["column"],
            "on_fail": r["on_fail"],
            "pass_count": r["pass_count"],
            "fail_count": r["fail_count"],
            "skipped": r["skipped"],
        }
        for r in validation_result["rule_results"]
    ]

    return {
        "source": validation_result["source"],
        "row_count": row_count,
        "missing_columns": validation_result["missing_columns"],
        "quarantined_count": int(validation_result["quarantine_mask"].sum()),
        "warned_count": int(validation_result["warn_mask"].sum()),
        "rule_breakdown": rule_breakdown,
    }
