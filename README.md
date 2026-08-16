# NovaMart — End-to-End Data Pipeline

A production-grade, continuously-running data pipeline that ingests messy multi-channel retail
data from 6 sources, profiles and validates data quality, cleans and transforms 1M+ records
through a layered warehouse architecture (SQLite → DuckDB → BigQuery), and delivers interactive
business dashboards.

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for the full technical specification and
[docs/](./docs/) for as-built documentation:

- [`docs/architecture.md`](./docs/architecture.md) — the 5-layer pipeline, orchestration, what's actually populated
- [`docs/data_dictionary.md`](./docs/data_dictionary.md) — every table/column the pipeline writes
- [`docs/data_simulator.md`](./docs/data_simulator.md) — how the 2-year synthetic source data is generated
- [`docs/incremental_load_design.md`](./docs/incremental_load_design.md) — how re-runs stay idempotent
- [`docs/docker_guide.md`](./docs/docker_guide.md) — running the pipeline + dashboard in containers
- [`docs/runbook.md`](./docs/runbook.md) — run modes, scheduled automation, troubleshooting

## Architecture

```
data/incoming/  →  INGEST  →  PROFILE  →  CLEAN/DEDUP  →  CANONICAL MAP
                                                                  │
                          DASHBOARD  ←  LOAD  ←  VALIDATE/QUARANTINE
                        (Streamlit)   (DuckDB +      (post-mapping,
                                       BigQuery)    business rules)
```

Six sources (Shopify, Amazon, POS, FedEx/UPS/USPS shipping, products, customers) feed a
canonical `stg_orders` table plus `fact_shipments`/`fact_inventory_daily`, from which five
pre-aggregated marts (revenue, customer LTV/RFM, product performance, inventory health, channel
performance) are built every run. Prefect orchestrates; every task wraps a plain, independently
testable Python function. Full diagram and rationale in
[`docs/architecture.md`](./docs/architecture.md).

## Status

Phases 1-7 complete: simulator, ingestion, profiling/quality-gate, validation/cleaning/dedup,
transform/load, orchestration/monitoring/Docker, and dashboards + documentation. Live Streamlit
Cloud deployment is not yet published — run locally or via `docker compose up` (see Quickstart).

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env
python scripts/generate_historical_data.py
python scripts/run_pipeline.py --mode full-refresh
streamlit run dashboard/app.py
```

Other run modes (see [`docs/runbook.md`](./docs/runbook.md)):

```bash
python scripts/run_pipeline.py --mode incremental
python scripts/run_pipeline.py --mode rebuild-marts --scope daily
python scripts/run_pipeline.py --mode backfill --start-date 2024-01-01 --end-date 2024-06-30
python scripts/run_pipeline.py --mode export --formats csv excel pdf
python scripts/run_pipeline.py --mode dry-run
```

Or via Docker (see [`docs/docker_guide.md`](./docs/docker_guide.md)):

```bash
docker compose up
```

## Testing

```bash
pytest -v --cov=src --cov-report=term-missing
ruff check .
```

## License

[MIT](./LICENSE)
