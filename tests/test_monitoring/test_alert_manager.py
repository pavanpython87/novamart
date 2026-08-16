from src.monitoring.alert_manager import AlertManager


def test_pass_scorecard_produces_no_alerts():
    alerts = AlertManager().evaluate_scorecard("shopify", {"outcome": "PASS", "reasons": []})
    assert alerts == []


def test_fail_scorecard_produces_error_alert_per_reason():
    alerts = AlertManager().evaluate_scorecard(
        "amazon",
        {"outcome": "FAIL", "reasons": ["missing columns: ['x']", "row count dropped 60%"]},
    )
    assert len(alerts) == 2
    assert all(a["severity"] == "error" for a in alerts)
    assert all(a["source"] == "amazon" for a in alerts)


def test_warn_scorecard_produces_warning_alerts():
    alerts = AlertManager().evaluate_scorecard(
        "pos", {"outcome": "WARN", "reasons": ["null % spike"]},
    )
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "warn"


def test_evaluate_usage_thresholds():
    manager = AlertManager()
    warn = manager.evaluate_usage({"storage_pct": 85, "query_pct": 10})
    assert len(warn) == 1
    assert warn[0]["severity"] == "warn"
    assert warn[0]["condition"] == "bigquery_storage_pct"

    errors = manager.evaluate_usage({"storage_pct": 97, "query_pct": 96})
    assert len(errors) == 2
    assert all(a["severity"] == "error" for a in errors)

    assert manager.evaluate_usage({"storage_pct": 10, "query_pct": 10}) == []
