from src.orchestration.tasks.notify_tasks import send_alerts


def test_send_alerts_calls_notifier_and_returns_count():
    sent = []
    result = send_alerts.fn(
        [{"severity": "warn", "condition": "row_count_drop", "message": "dropped 30%"}],
        notifier=sent.append,
    )
    assert result == 1
    assert len(sent) == 1


def test_send_alerts_empty_list_skips_notifier():
    calls = []
    result = send_alerts.fn([], notifier=lambda alerts: calls.append(alerts))
    assert result == 0
    assert calls == []
