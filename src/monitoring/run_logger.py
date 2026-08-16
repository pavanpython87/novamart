"""Append-only JSONL pipeline run log.

Every pipeline run (incremental, full refresh, backfill, rebuild-marts,
export) writes one line to data/logs/run_history.jsonl so the audit trail
is a simple, greppable, append-only file rather than a database. One line
per run, JSON-serialised, never modified after write.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DEFAULT_RUN_LOG = Path("data/logs/run_history.jsonl")


class RunLogger:
    def __init__(self, log_path: str | Path = DEFAULT_RUN_LOG):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_run(self, run_summary: dict) -> dict:
        """Appends one run entry to the log and returns the persisted entry
        (with its `logged_at` timestamp added)."""
        entry = {
            "logged_at": dt.datetime.now(dt.UTC).isoformat(),
            **run_summary,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def load_runs(self, limit: int | None = None) -> list[dict]:
        """Returns all logged runs (most recent last), optionally capped to
        the last `limit` entries. A missing log file yields an empty list."""
        if not self.log_path.exists():
            return []
        runs: list[dict] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    runs.append(json.loads(line))
        if limit is not None:
            runs = runs[-limit:]
        return runs

    def last_run(self) -> dict | None:
        runs = self.load_runs(limit=1)
        return runs[-1] if runs else None
