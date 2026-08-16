"""Quality metric trending over time.

Appends a per-source, per-batch quality record (PASS/WARN/FAIL outcome,
reasons, and key profile metrics) to data/logs/quality_trend.jsonl so the
pipeline-health dashboard and post-mortems can chart quality drift across
runs. The file mirrors run_logger.py's append-only JSONL convention.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DEFAULT_QUALITY_LOG = Path("data/logs/quality_trend.jsonl")


class QualityTracker:
    def __init__(self, log_path: str | Path = DEFAULT_QUALITY_LOG):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        batch_id: str,
        source: str,
        outcome: str,
        reasons: list[str] | None = None,
        metrics: dict | None = None,
    ) -> dict:
        """Appends one quality record and returns it."""
        entry = {
            "recorded_at": dt.datetime.now(dt.UTC).isoformat(),
            "batch_id": batch_id,
            "source": source,
            "outcome": outcome,
            "reasons": reasons or [],
            "metrics": metrics or {},
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def record_scorecard(self, batch_id: str, source: str, scorecard: dict,
                          profile: dict | None = None) -> dict:
        """Convenience wrapper that extracts outcome/reasons from a
        quality_scorecard.score_batch result and stores row/column counts
        from the accompanying profile (if provided) as metrics."""
        metrics: dict = {}
        if profile:
            metrics["row_count"] = profile.get("row_count")
            metrics["column_count"] = profile.get("column_count")
        return self.record(
            batch_id,
            source,
            scorecard.get("outcome", "PASS"),
            scorecard.get("reasons", []),
            metrics,
        )

    def load_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        records: list[dict] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def trend(self, source: str | None = None) -> list[dict]:
        """Returns quality records, optionally filtered to a single source."""
        records = self.load_all()
        if source is not None:
            records = [r for r in records if r.get("source") == source]
        return records
