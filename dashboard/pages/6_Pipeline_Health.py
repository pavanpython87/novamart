"""Dashboard 6 — Pipeline health & monitoring.

Run history, quality trends, quarantine queue, and warehouse schema state,
drawn from the monitoring layer's JSONL logs and the landing/quarantine
databases.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.ui import empty_state, format_number, metric_row
from dashboard.db_connector import get_client
from src.monitoring.quality_tracker import QualityTracker
from src.monitoring.run_logger import RunLogger

st.set_page_config(page_title="Pipeline Health", layout="wide", page_icon="🩺")

client = get_client()

st.title("Pipeline Health")
st.caption("Run history, quality trends, and quarantine queue at a glance.")

DEFAULT_RUN_LOG = "data/logs/run_history.jsonl"
DEFAULT_QUALITY_LOG = "data/logs/quality_trend.jsonl"
DEFAULT_QUARANTINE_DB = "data/quarantine/novamart_quarantine.db"

# -- run history --------------------------------------------------------
runs = RunLogger(DEFAULT_RUN_LOG).load_runs()

if runs:
    latest = runs[-1]
    mode = latest.get("mode", "?")
    order_count = latest.get("order_row_count", latest.get("order_row_count", 0))
    tables_written = len(latest.get("tables_written", []) or [])

    metric_row([
        ("Total runs", format_number(len(runs)), None),
        ("Last mode", mode, None),
        ("Last batch orders", format_number(order_count), None),
        ("Last tables written", format_number(tables_written), None),
    ])

    st.subheader("Run history")
    run_df = pd.DataFrame(runs).tail(50)
    if "logged_at" in run_df:
        run_df = run_df.sort_values("logged_at")
        fig = px.line(
            run_df, x="logged_at", y="order_row_count",
            labels={"logged_at": "", "order_row_count": "Orders processed"},
        )
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(run_df.tail(20), use_container_width=True, hide_index=True)
else:
    empty_state("No pipeline runs logged yet.", icon="🚧")

# -- quality trend ------------------------------------------------------
quality = QualityTracker(DEFAULT_QUALITY_LOG).load_all()
if quality:
    st.subheader("Quality trend")
    qdf = pd.DataFrame(quality)
    if {"recorded_at", "outcome", "source"}.issubset(qdf.columns):
        counts = qdf.groupby(["recorded_at", "outcome"]).size().reset_index(name="count")
        fig = px.scatter(
            counts, x="recorded_at", y="outcome", size="count", color="outcome",
            labels={"recorded_at": "", "outcome": "Quality gate outcome"},
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

    by_source = qdf.groupby("source")["outcome"].value_counts().unstack(fill_value=0)
    st.dataframe(by_source, use_container_width=True)
else:
    empty_state("No quality-trend records yet.", icon="🚧")

# -- quarantine queue ---------------------------------------------------
quarantine_path = Path(DEFAULT_QUARANTINE_DB)
if quarantine_path.exists():
    st.subheader("Quarantine queue")
    conn = sqlite3.connect(quarantine_path)
    try:
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'quarantine_%'"
            ).fetchall()
        ]
        counts = {}
        for table in tables:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()

    if counts:
        qcounts = pd.DataFrame(
            [{"table": k, "records": v} for k, v in counts.items()]
        ).sort_values("records", ascending=False)
        fig = px.bar(qcounts, x="table", y="records",
                     labels={"records": "Quarantined records", "table": ""})
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(qcounts, use_container_width=True, hide_index=True)
    else:
        st.write("Quarantine database is empty. 🎉")
else:
    st.write("No quarantine database yet.")

# -- warehouse schema / usage -------------------------------------------
st.subheader("Warehouse schema")
tables = client.list_tables()
if tables:
    st.write(f"{len(tables)} tables in the serving warehouse:")
    st.code("\n".join(tables), language=None)
else:
    empty_state("Serving warehouse has no tables yet.", icon="🚧")

if client.backend == "bigquery":
    st.subheader("BigQuery usage (free-tier watchdog)")
    from src.monitoring.bigquery_usage_tracker import BigQueryUsageTracker

    try:
        usage = BigQueryUsageTracker(client.project_id).check_usage()
        metric_row([
            ("Storage", f"{usage['storage_pct']:.2f}% of 10 GB", None),
            ("Query bytes", f"{usage['query_pct']:.2f}% of 1 TB", None),
        ])
    except Exception as exc:  # pragma: no cover - depends on live GCP
        st.warning(f"Could not read BigQuery usage: {exc}")
else:
    st.caption("DuckDB backend — BigQuery usage tracking is disabled.")
