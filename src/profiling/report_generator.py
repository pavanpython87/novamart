"""Writes JSON + HTML profiling reports per source per batch to
data/profiling_reports/, combining the raw profile with its quality
scorecard outcome.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DEFAULT_REPORT_DIR = Path("data/profiling_reports")

_OUTCOME_COLORS = {"PASS": "#2e7d32", "WARN": "#f9a825", "FAIL": "#c62828"}


def _report_stem(source: str, timestamp: dt.datetime) -> str:
    return f"{source}_{timestamp.strftime('%Y%m%dT%H%M%S')}"


def _render_html(source: str, profile: dict, scorecard: dict, timestamp: dt.datetime) -> str:
    outcome = scorecard["outcome"]
    color = _OUTCOME_COLORS.get(outcome, "#555")
    reasons_html = "".join(f"<li>{r}</li>" for r in scorecard["reasons"]) or "<li>none</li>"
    columns_html = "".join(
        f"<tr><td>{col}</td><td>{c['dtype']}</td><td>{c['null_pct']}%</td>"
        f"<td>{c['distinct_count']}</td></tr>"
        for col, c in profile["columns"].items()
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Profiling report: {source}</title></head>
<body>
<h1>{source}</h1>
<p>Generated: {timestamp.isoformat()}</p>
<h2 style="color:{color}">Outcome: {outcome}</h2>
<ul>{reasons_html}</ul>
<p>Rows: {profile["row_count"]} | Columns: {profile["column_count"]}</p>
<table border="1" cellpadding="4">
<tr><th>Column</th><th>Dtype</th><th>Null %</th><th>Distinct</th></tr>
{columns_html}
</table>
</body>
</html>"""


def generate_report(source: str, profile: dict, scorecard: dict,
                     output_dir: str | Path = DEFAULT_REPORT_DIR,
                     timestamp: dt.datetime | None = None) -> dict[str, Path]:
    """Writes both JSON and HTML reports; returns their paths."""
    timestamp = timestamp or dt.datetime.now(dt.UTC)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _report_stem(source, timestamp)

    json_path = output_dir / f"{stem}.json"
    html_path = output_dir / f"{stem}.html"

    payload = {
        "source": source,
        "generated_at": timestamp.isoformat(),
        "profile": profile,
        "scorecard": scorecard,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    html_path.write_text(_render_html(source, profile, scorecard, timestamp), encoding="utf-8")

    return {"json": json_path, "html": html_path}
