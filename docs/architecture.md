# Architecture

NovaMart's pipeline moves data through five layers, each independently
testable and each tolerant of the layer before it failing partially. Every
layer is a plain Python module under `src/`; Prefect (`src/orchestration/`)
wires them into flows but contains no business logic of its own — every
task is a thin wrapper around a function you can call and test directly.

```
data/incoming/*                  (files dropped by the simulator / real feeds)
        │
        ▼
┌─────────────────┐   SHA-256 file registry / high-water-mark
│   INGESTION      │   src/ingestion/  (csv, excel, json, xml, sqlite,
│                  │   flat-file connectors + incremental_tracker.py)
└─────────────────┘
        │  raw per-channel DataFrame, native column names
        ▼
┌─────────────────┐   ydata-profiling-style stats + baseline drift check
│   PROFILING      │   src/profiling/  (profiler.py, baseline_manager.py,
│                  │   drift_detector.py, quality_scorecard.py)
└─────────────────┘
        │  scorecard (PASS/WARN/FAIL) logged, data passed through unchanged
        ▼
┌─────────────────┐   dedup (order lines, customers) + field normalizers
│  CLEANING/DEDUP  │   src/cleaning/, src/dedup/
└─────────────────┘
        │
        ▼
┌─────────────────┐   shopify/amazon/pos → canonical order-line shape
│ CANONICAL MAP +  │   fedex/ups/usps → canonical shipment shape
│   TRANSFORM      │   src/orchestration/canonical_mapping.py,
│                  │   src/transform/ (revenue_calculator, mart_builder, ...)
└─────────────────┘
        │  canonical orders / shipments DataFrames
        ▼
┌─────────────────┐   business-rule validation now runs HERE (post-mapping,
│ VALIDATE/        │   see "Why validation runs after mapping" below) —
│ QUARANTINE       │   src/validation/ (rules_engine.py, quarantine_manager.py)
└─────────────────┘
        │  clean rows only; quarantined rows → SQLite quarantine DB
        ▼
┌─────────────────┐   DuckDB (always) + BigQuery (optional, WAREHOUSE_BACKEND)
│   LOAD           │   src/load/ (duckdb_loader.py, schema_manager.py,
│                  │   fact_builders.py, dual_loader.py, bigquery_loader.py)
└─────────────────┘
        │
        ▼
┌─────────────────┐   6 pages, DuckDB or BigQuery, cached queries
│   DASHBOARD      │   dashboard/ (Streamlit + Plotly)
└─────────────────┘
```

## Orchestration: flows and tasks

`src/orchestration/flows/main_pipeline.py` is the single flow every other
mode wraps. Its shape:

```
_ingest_all_sources          ingest every configured source (independent
                              per-source try/except — one source's ingestion
                              failure never blocks the others)
        │
_profile_sources              per-source profiling scorecards only
        │
build_orders                  dedup → canonical field mapping → SKU
                               resolution → revenue economics, for
                               shopify/amazon/pos
        │
_validate_canonical(orders)   business rules + quarantine, on canonical data
        │
build_shipments_fact          fedex/ups/usps → one canonical shape
        │
_validate_canonical(shipments)
        │
build_all_marts               5 pre-aggregated mart tables
        │
DuckDBLoader / write_duckdb_tables / upsert   → data/serving/*.duckdb
```

Six run modes (`scripts/run_pipeline.py --mode ...`) each wrap
`main_pipeline` differently — see `docs/runbook.md` for what each one does
and when to use it.

Prefect gives this two things worth the dependency: automatic retries
(`retries=3` on ingestion/load tasks, for transient failures) and a
task-level run log. It deliberately does **not** run sources in parallel —
`IncrementalTracker` and `QuarantineManager` each hold a single sqlite3
connection that isn't thread-safe, and at this pipeline's scale (8 sources,
once a day) there's nothing to gain from concurrency.

## Why validation runs after canonical mapping

Each channel's raw file uses its own native column names — Shopify's
`Total`/`Created at`, Amazon's `item-price` (hyphenated), FedEx's
`TrackingNumber`/`ShipDate` (PascalCase). `config/quality_rules.yaml`
defines business rules once, in terms of the *canonical* schema
(`order_id`, `gross_revenue`, `order_date`, `tracking_number`,
`ship_date_key`, ...). Running validation before the raw→canonical mapping
step means the rule engine is checking columns that don't exist under
those names yet — every rule silently skips (this was a real bug: see the
git history around `_validate_canonical`). Validation now runs on the
canonical `orders` and `shipments` DataFrames, straight after
`build_orders()`/`build_shipments_fact()`, so one rule set correctly
covers every channel.

## Data model: what's actually populated

`src/load/schema_manager.py` defines a full dimensional star schema
(`dim_customers`, `dim_products`, `dim_dates`, `dim_channels`,
`fact_orders`, `fact_returns`, `fact_shipments`, `fact_inventory_daily`).
`DuckDBLoader.create_schema()` creates all of these tables. In the current
implementation, only some of them are actually written to by
`main_pipeline`:

| Table | Populated? | Written by |
|---|---|---|
| `stg_orders` | Yes | `main_pipeline` — flat, cumulative canonical order-line table (not `fact_orders`; there's no separate `dim_customers`/`dim_products` join, the flat table carries everything the marts need) |
| `mart_revenue_daily`, `mart_customer_ltv`, `mart_product_performance`, `mart_inventory_health`, `mart_channel_performance` | Yes | `main_pipeline` / `rebuild_marts_flow` — pre-aggregated from `stg_orders` |
| `fact_shipments` | Yes | `main_pipeline`, keyed upsert on `tracking_number` |
| `fact_inventory_daily` | Yes | `main_pipeline`, keyed upsert on `product_key` |
| `dim_customers`, `dim_products`, `dim_dates`, `dim_channels`, `fact_orders`, `fact_returns` | No — schema exists (empty tables), nothing populates them | — |

The dashboards and marts read `stg_orders` directly rather than a
normalized dim/fact join, which is simpler and fast enough at this data
volume (DuckDB, single-digit millions of rows). The unused dim/fact tables
are a natural next step if the model needs to scale to a real star-schema
BI tool.

## Monitoring

`src/monitoring/` is append-only-JSONL based, not a database:

- `run_logger.py` → `data/logs/run_history.jsonl` — one line per pipeline
  run (mode, batch_id, row counts, tables written).
- `quality_tracker.py` → `data/logs/quality_trend.jsonl` — one line per
  source per batch (PASS/WARN/FAIL outcome + reasons), so quality drift is
  chartable over time on the Pipeline Health dashboard.
- `alert_manager.py` — turns FAIL/WARN scorecards and BigQuery usage
  snapshots into alert dicts; `notify_tasks.send_alerts` dispatches them
  (logs by default — the notifier is swappable for Slack/email/PagerDuty
  without touching flow code).
- `bigquery_usage_tracker.py` — watches BigQuery's free-tier storage/query
  limits so a runaway job doesn't produce a surprise bill.

## Local vs cloud warehouse

`WAREHOUSE_BACKEND` (`duckdb` | `bigquery` | `both`) controls where
`main_pipeline` and the dashboard write/read data:

- `duckdb` (default): everything runs locally, zero external dependencies
  or credentials — this is what `docker compose up` and local development
  use.
- `bigquery` / `both`: `src/load/dual_loader.py` writes to DuckDB and
  BigQuery in the same run; the dashboard (`dashboard/db_connector.py`)
  prefers BigQuery when `BQ_PROJECT_ID`/`GOOGLE_APPLICATION_CREDENTIALS`
  are set, and falls back to DuckDB automatically if they aren't — the
  dashboard always renders even with no cloud credentials configured.

See `docs/data_dictionary.md` for full table/column definitions and
`docs/incremental_load_design.md` for how idempotency is guaranteed across
re-runs.
