import pandas as pd

from src.transform.shipping_analytics import (
    calculate_delivery_days,
    calculate_on_time_rate,
    calculate_shipping_cost_pct_of_revenue,
    carrier_performance,
)

SHIPMENTS = pd.DataFrame([
    {"tracking_number": "T1", "carrier": "UPS", "ship_date": "2024-03-01",
     "delivery_date": "2024-03-03", "promised_delivery_date": "2024-03-04", "shipping_cost": 5.0},
    {"tracking_number": "T2", "carrier": "UPS", "ship_date": "2024-03-01",
     "delivery_date": "2024-03-06", "promised_delivery_date": "2024-03-04", "shipping_cost": 5.0},
    {"tracking_number": "T3", "carrier": "FedEx", "ship_date": "2024-03-01",
     "delivery_date": "2024-03-02", "promised_delivery_date": "2024-03-03", "shipping_cost": 8.0},
])

ORDERS = pd.DataFrame([
    {"gross_revenue": 100.0},
    {"gross_revenue": 100.0},
])


def test_calculate_delivery_days():
    result = calculate_delivery_days(SHIPMENTS).set_index("tracking_number")
    assert result.loc["T1", "delivery_days"] == 2
    assert result.loc["T2", "delivery_days"] == 5


def test_calculate_on_time_rate():
    result = calculate_on_time_rate(SHIPMENTS).set_index("tracking_number")
    assert bool(result.loc["T1", "on_time"]) is True
    assert bool(result.loc["T2", "on_time"]) is False


def test_carrier_performance():
    result = carrier_performance(SHIPMENTS).set_index("carrier")
    assert result.loc["UPS", "shipment_count"] == 2
    assert result.loc["UPS", "on_time_rate"] == 0.5
    assert result.loc["FedEx", "on_time_rate"] == 1.0


def test_calculate_shipping_cost_pct_of_revenue():
    pct = calculate_shipping_cost_pct_of_revenue(SHIPMENTS, ORDERS)
    assert pct == round(18.0 / 200.0, 4)


def test_calculate_shipping_cost_pct_of_revenue_zero_revenue():
    empty_orders = pd.DataFrame(columns=["gross_revenue"])
    assert calculate_shipping_cost_pct_of_revenue(SHIPMENTS, empty_orders) == 0.0
