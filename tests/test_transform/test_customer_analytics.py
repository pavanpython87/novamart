import pandas as pd

from src.transform.customer_analytics import (
    build_customer_analytics,
    calculate_aov,
    calculate_clv,
    calculate_purchase_frequency,
    calculate_rfm,
    score_churn_risk,
)

ORDERS = pd.DataFrame([
    {"customer_key": "A", "order_date": "2024-01-01", "net_revenue": 100.0},
    {"customer_key": "A", "order_date": "2024-01-10", "net_revenue": 150.0},
    {"customer_key": "B", "order_date": "2023-06-01", "net_revenue": 50.0},
    {"customer_key": "C", "order_date": "2024-02-01", "net_revenue": 10.0},
    {"customer_key": "C", "order_date": "2024-02-15", "net_revenue": 20.0},
    {"customer_key": "C", "order_date": "2024-03-01", "net_revenue": 30.0},
])

AS_OF = pd.Timestamp("2024-03-15")


def test_calculate_aov():
    result = calculate_aov(ORDERS).set_index("customer_key")["aov"]
    assert result["A"] == 125.0
    assert result["C"] == 20.0


def test_calculate_clv():
    result = calculate_clv(ORDERS).set_index("customer_key")["clv"]
    assert result["A"] == 250.0
    assert result["C"] == 60.0


def test_calculate_purchase_frequency():
    result = calculate_purchase_frequency(ORDERS).set_index("customer_key")["purchase_frequency"]
    assert result["A"] == 2
    assert result["B"] == 1
    assert result["C"] == 3


def test_score_churn_risk_buckets():
    result = score_churn_risk(ORDERS, as_of=AS_OF).set_index("customer_key")
    assert result.loc["C", "churn_risk"] == "low"
    assert result.loc["A", "churn_risk"] == "medium"
    assert result.loc["B", "churn_risk"] == "lost"


def test_calculate_rfm_monetary_and_frequency_values():
    result = calculate_rfm(ORDERS, as_of=AS_OF).set_index("customer_key")
    assert result.loc["A", "frequency"] == 2
    assert result.loc["C", "monetary"] == 60.0
    # more recent + more frequent + higher spend customers should score higher
    assert result.loc["C", "r_score"] > result.loc["B", "r_score"]
    assert result.loc["C", "f_score"] >= result.loc["B", "f_score"]
    assert len(result.loc["C", "rfm_segment"]) == 3
    assert result.loc["C", "rfm_segment"].isdigit()


def test_calculate_rfm_empty_returns_expected_columns():
    result = calculate_rfm(pd.DataFrame(columns=["customer_key", "order_date", "net_revenue"]))
    assert list(result.columns) == [
        "customer_key", "recency", "frequency", "monetary",
        "r_score", "f_score", "m_score", "rfm_segment",
    ]
    assert result.empty


def test_build_customer_analytics_combines_all_metrics():
    result = build_customer_analytics(ORDERS, as_of=AS_OF).set_index("customer_key")
    assert result.loc["A", "aov"] == 125.0
    assert result.loc["A", "clv"] == 250.0
    assert result.loc["A", "purchase_frequency"] == 2
    assert result.loc["A", "churn_risk"] == "medium"
    assert "rfm_segment" in result.columns


def test_build_customer_analytics_empty():
    result = build_customer_analytics(pd.DataFrame(columns=["customer_key", "order_date", "net_revenue"]))
    assert result.empty
