# NovaMart — End-to-End Data Pipeline

A production-grade, continuously-running data pipeline that ingests messy multi-channel retail
data from 6 sources, profiles and validates data quality, cleans and transforms 1M+ records
through a layered warehouse architecture (SQLite → DuckDB → BigQuery), and delivers interactive
business dashboards.

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for the full technical specification.

## Status

🚧 In development — Phase 6 (Dashboards) complete.
Phases 1-5 (simulator, ingestion, validation/cleaning/dedup, transform/load,
orchestration/monitoring/Docker) are done.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/generate_historical_data.py
python scripts/run_pipeline.py --mode full-refresh
streamlit run dashboard/app.py
```

Other run modes (see PROJECT_PLAN.md 3.2):

```bash
python scripts/run_pipeline.py --mode incremental
python scripts/run_pipeline.py --mode rebuild-marts --scope daily
python scripts/run_pipeline.py --mode backfill --start-date 2024-01-01 --end-date 2024-06-30
python scripts/run_pipeline.py --mode export --formats csv excel pdf
python scripts/run_pipeline.py --mode dry-run
```

Or via Docker:

```bash
docker compose up
```
