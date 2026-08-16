"""Threshold-based alerting.

Turns two kinds of inputs into a list of alert dicts that
orchestration.tasks.notify_tasks.send_alerts knows how to dispatch:

  - a quality scorecard (PASS/WARN/FAIL) from quality_scorecard.score_batch
  - a usage snapshot from bigquery_usage_tracker.check_usage

Alerts are plain dicts with `severity` ("info"|"warn"|"error"),
`condition`, and `message` keys so a real Slack/email/PagerDuty notifier
can be swapped in without touching flow code.
"""

from __future__ import annotations

SEVERITY_BY_OUTCOME = {"PASS": "info", "WARN": "warn", "FAIL": "error"}

DEFAULT_USAGE_WARN_PCT = 80
DEFAULT_USAGE_ALERT_PCT = 95


class AlertManager:
    def __init__(self, usage_warn_pct: float = DEFAULT_USAGE_WARN_PCT,
                  usage_alert_pct: float = DEFAULT_USAGE_ALERT_PCT):
        self.usage_warn_pct = usage_warn_pct
        self.usage_alert_pct = usage_alert_pct

    def evaluate_scorecard(self, source: str, scorecard: dict) -> list[dict]:
        """Returns an alert per FAIL/WARN reason. PASS scorecards produce no
        alerts (a clean run is the absence of alerts, not an event)."""
        outcome = scorecard.get("outcome", "PASS")
        if outcome == "PASS":
            return []

        severity = SEVERITY_BY_OUTCOME.get(outcome, "warn")
        return [
            {
                "severity": severity,
                "condition": f"{source}_quality_gate",
                "message": f"{source}: {reason}",
                "source": source,
                "outcome": outcome,
            }
            for reason in scorecard.get("reasons", [])
        ]

    def evaluate_usage(self, usage: dict) -> list[dict]:
        """Emits a warn/error alert as BigQuery storage or query usage
        approaches the free-tier limit (defaults: warn at 80%, alert at
        95%). `usage` is the dict returned by
        bigquery_usage_tracker.BigQueryUsageTracker.check_usage."""
        alerts: list[dict] = []
        for metric, pct in (("storage_pct", usage.get("storage_pct", 0)),
                            ("query_pct", usage.get("query_pct", 0))):
            if pct >= self.usage_alert_pct:
                alerts.append({
                    "severity": "error",
                    "condition": f"bigquery_{metric}",
                    "message": f"BigQuery {metric} at {pct:.2f}% of free tier — "
                               f"stop loads or upgrade before the limit is hit",
                })
            elif pct >= self.usage_warn_pct:
                alerts.append({
                    "severity": "warn",
                    "condition": f"bigquery_{metric}",
                    "message": f"BigQuery {metric} at {pct:.2f}% of free tier",
                })
        return alerts
