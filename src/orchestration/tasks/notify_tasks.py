"""Alert dispatch task: takes already-evaluated alerts (see
src.monitoring.alert_manager) and sends them somewhere a human will see
them. Logs by default; the notifier is injectable so a real
Slack/email/PagerDuty integration can be swapped in later without
touching flow code.
"""

from __future__ import annotations

import logging

from prefect import task

logger = logging.getLogger(__name__)


def log_notifier(alerts: list[dict]) -> None:
    for alert in alerts:
        logger.warning("ALERT [%s] %s: %s", alert.get("severity", "warn"), alert.get("condition"), alert.get("message"))


@task(name="send-alerts")
def send_alerts(alerts: list[dict], notifier=log_notifier) -> int:
    """Dispatches each alert via `notifier` (defaults to logging). Returns
    the number of alerts sent."""
    if not alerts:
        return 0
    notifier(alerts)
    return len(alerts)
