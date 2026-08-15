# NovaMart — End-to-End Data Pipeline

A production-grade, continuously-running data pipeline that ingests messy multi-channel retail
data from 6 sources, profiles and validates data quality, cleans and transforms 1M+ records
through a layered warehouse architecture (SQLite → DuckDB → BigQuery), and delivers interactive
business dashboards.

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for the full technical specification.

## Status

🚧 In development — Phase 1 (Foundation + data simulator).

## Quickstart (once Phase 1-4 are complete)

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/generate_historical_data.py
python scripts/run_pipeline.py --mode full-refresh
streamlit run dashboard/app.py
```

Or via Docker:

```bash
docker compose up
```
