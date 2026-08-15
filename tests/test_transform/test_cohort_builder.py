import pandas as pd

from src.transform.cohort_builder import assign_cohorts, build_cohort_sizes, build_retention_matrix

ORDERS = pd.DataFrame([
    {"customer_key": "A", "order_date": "2024-01-05"},
    {"customer_key": "A", "order_date": "2024-02-10"},
    {"customer_key": "B", "order_date": "2024-01-20"},
    {"customer_key": "C", "order_date": "2024-02-01"},
])


def test_assign_cohorts():
    result = assign_cohorts(ORDERS)
    a_rows = result[result["customer_key"] == "A"]
    assert (a_rows["acquisition_month"] == pd.Period("2024-01", freq="M")).all()
    c_rows = result[result["customer_key"] == "C"]
    assert (c_rows["acquisition_month"] == pd.Period("2024-02", freq="M")).all()


def test_build_cohort_sizes():
    result = build_cohort_sizes(ORDERS).set_index("acquisition_month")
    assert result.loc[pd.Period("2024-01", freq="M"), "cohort_size"] == 2
    assert result.loc[pd.Period("2024-02", freq="M"), "cohort_size"] == 1


def test_build_retention_matrix():
    result = build_retention_matrix(ORDERS)
    jan_cohort = result[result["acquisition_month"] == pd.Period("2024-01", freq="M")]
    month0 = jan_cohort[jan_cohort["period_offset"] == 0]
    month1 = jan_cohort[jan_cohort["period_offset"] == 1]
    assert month0["active_customers"].iloc[0] == 2
    assert month0["retention_rate"].iloc[0] == 1.0
    # Only A came back in month offset 1 (Feb), out of a cohort of 2
    assert month1["active_customers"].iloc[0] == 1
    assert month1["retention_rate"].iloc[0] == 0.5


def test_build_retention_matrix_empty():
    result = build_retention_matrix(pd.DataFrame(columns=["customer_key", "order_date"]))
    assert result.empty
