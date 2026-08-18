# Runbook

How to run, troubleshoot, and extend the NovaMart pipeline. Every mode
below is invoked through the single CLI entry point,
`scripts/run_pipeline.py --mode ...`, which every schedule (GitHub
Actions), Docker, and local development path uses.

## Run modes

```bash
python scripts/run_pipeline.py --mode incremental
python scripts/run_pipeline.py --mode full-refresh
python scripts/run_pipeline.py --mode rebuild-marts --scope daily|weekly|all
python scripts/run_pipeline.py --mode backfill --start-date 2024-01-01 --end-date 2024-06-30
python scripts/run_pipeline.py --mode export --formats csv excel pdf
python scripts/run_pipeline.py --mode dry-run
```

### `incremental` (default, daily)

`incremental_flow` → `main_pipeline` once, then logs the run to
`data/logs/run_history.jsonl`, records each source's quality scorecard to
`data/logs/quality_trend.jsonl`, and dispatches any quality-gate alerts
via `notify_tasks.send_alerts`. This is what `main_pipeline` already does
incrementally on its own (file registry / high-water-mark skip
already-seen data, see `docs/incremental_load_design.md`) — this flow just
adds the monitoring layer on top. Use for normal day-to-day runs against
whatever new files have landed in `data/incoming/`.

### `full-refresh` (monthly)

`full_refresh_flow` deletes the incremental tracker DB, quarantine DB,
serving DuckDB file, and (by default) the profiling baseline directory,
then runs `main_pipeline` once against **every** file currently in
`data/incoming/` — since the tracker is gone, nothing is "already seen."
Use after a transformation-logic change that needs to apply to all
historical data, or to recover from serving-warehouse corruption. This is
destructive to local state (not to `data/incoming/` itself) — the run log
records what was reset (`result["reset"]`) so you can confirm afterward.

### `rebuild-marts --scope {daily,weekly,all}`

`rebuild_marts_flow` re-reads `stg_orders` from the serving warehouse and
recomputes marts — no re-ingestion, re-cleaning, or re-validation.
`--scope daily` rebuilds `mart_revenue_daily` + `mart_channel_performance`
(cheap, matches the daily schedule); `--scope weekly` rebuilds
`mart_customer_ltv` + `mart_product_performance` +
`mart_inventory_health` (heavier RFM/sell-through math, matches the
weekly schedule); `--scope all` rebuilds all five (used by
`full-refresh`'s follow-up step and manual rebuilds). Use this alone when
mart-building logic changed but ingestion/staging didn't — much faster
than a full refresh.

### `backfill --start-date ... --end-date ...`

`backfill_flow` calls the data simulator (`simulate_data`, see
`docs/data_simulator.md`) to generate files for `[start_date, end_date]`
into `data/incoming/`, then runs `main_pipeline` once. Because the file
registry hashes content, re-running a backfill over an already-processed
range only re-ingests files whose bytes actually changed (e.g. regenerated
with a different `--chaos-level`/`--seed`). Also accepts `--seed` and
`--chaos-level` (passed straight to the simulator — see
`docs/data_simulator.md` for what each controls). This is the only mode
that *generates* source data rather than consuming what's already in
`data/incoming/`; every other mode assumes files already exist there
(from a prior backfill, the daily GitHub Actions simulation step, or real
upstream feeds in a non-simulated deployment).

### `export --formats csv excel pdf`

`export_flow` reads whichever mart tables currently exist and are
non-empty out of the serving warehouse and writes them to
`data/exports/` in the requested formats via `export_manager.export_marts`.
Read-only against the warehouse — safe to run any time, doesn't touch
ingestion/staging state.

### `dry-run`

Calls `main_pipeline(..., dry_run=True)` directly (not through any of the
monitoring/export wrapper flows) — use to validate config and connectivity
without mutating `data/serving/` or `data/quarantine/`.

## Scheduled automation (GitHub Actions)

| Workflow | Cron (UTC) | Runs |
|---|---|---|
| `daily_pipeline.yml` | `0 2 * * *` | `simulate_new_data.py --date yesterday` → `--mode incremental` → `--mode rebuild-marts --scope daily` → uploads `data/profiling_reports/` as a build artifact → commits `data/logs/` back to the repo |
| `weekly_rebuild.yml` | `0 4 * * 0` (Sundays) | `--mode rebuild-marts --scope weekly` → `--mode export --formats excel` → commits `data/logs/` + `data/exports/` |
| `monthly_refresh.yml` | `0 3 1 * *` (1st of month) | `--mode full-refresh` → `--mode rebuild-marts --scope all` → `--mode export --formats csv excel pdf` → commits `data/logs/` + `data/exports/` |
| `ci.yml` | on push/PR | test + lint gate (see below) |

All three scheduled workflows also accept `workflow_dispatch` for manual
triggering from the Actions tab. `WAREHOUSE_BACKEND` is set to `both` when
`vars.BQ_PROJECT_ID` is configured, `duckdb` otherwise — so these
workflows run against local DuckDB out of the box with zero required
config, and start writing to BigQuery automatically the moment the repo's
`BQ_PROJECT_ID`/`BQ_DATASET`/`GCP_WORKLOAD_IDENTITY_PROVIDER`/
`GCP_SERVICE_ACCOUNT` repo variables are configured. BigQuery auth uses
Workload Identity Federation (`google-github-actions/auth@v2`) rather than
a downloaded service account key — no long-lived credential is stored in
the repo. The commit-run-log steps use `|| true` on both `git commit` and
`git push` so a no-op day (nothing changed in `data/logs/`) doesn't fail
the workflow.

## Troubleshooting

**A source's ingestion is failing every run.** Each source ingests
independently (`_ingest_all_sources` in `main_pipeline.py` catches
per-source), so one broken source doesn't block the others — check the
run's logs for `"Skipping unparseable file"` (a single malformed file,
see `docs/incremental_load_design.md`) vs. a repeated task-level failure
after 3 retries (a real connector/config problem, e.g. a source path in
`config/pipeline_config.yaml` that doesn't exist).

**Quarantine table is unexpectedly empty (or unexpectedly huge).**
`config/quality_rules.yaml` rules apply to *canonical* column names
(`order_id`, `gross_revenue`, ...), evaluated after `build_orders()`/
`build_shipments_fact()`, not to raw per-channel columns — see
`docs/architecture.md`'s "Why validation runs after canonical mapping."
If a new rule doesn't seem to be firing, confirm the column name matches
the canonical schema in `docs/data_dictionary.md`, not the raw source
file's column.

**A Prefect task raises a hashing/pickle error
(`Unable to create hash ... could not be serialized`).** Any task
argument that wraps a live `sqlite3.Connection` or
`duckdb.DuckDBPyConnection` (`IncrementalTracker`, `QuarantineManager`,
`DuckDBLoader`, `DualLoader`) needs `cache_policy=NO_CACHE` on that task's
`@task(...)` decorator — Prefect can't hash a live connection object into
a cache key. See `src/orchestration/tasks/ingest_tasks.py` and
`load_tasks.py` for the pattern.

**Dashboard shows empty tables.** Either no pipeline run has completed
yet against this warehouse file (see `docs/docker_guide.md`'s note on
`depends_on` only controlling startup order, not run completion), or
`WAREHOUSE_BACKEND=bigquery`/`both` is set but BigQuery credentials are
missing — `dashboard/db_connector.py` falls back to DuckDB automatically
in that case, so check which backend it actually resolved to
(`_resolve_backend()`) if data seems stale relative to what a BigQuery-
targeted run produced.

**Re-running a mode seems to double data.** Shouldn't happen —
see `docs/incremental_load_design.md` for the three independent
idempotency layers (file registry, exact-row dedup on `stg_orders`, keyed
upsert on fact tables). If it does, it's a real bug: check which layer's
invariant broke (a new file source not registered with the tracker, a
new fact table not going through `DuckDBLoader.upsert`, etc.).

## CI gate (`ci.yml`)

Runs on every push/PR: `pytest -v --cov=src --cov-report=term-missing`
plus `ruff check`. Keep both green before merging — see
`docs/architecture.md` for the module layout `pytest`'s test tree mirrors
(`tests/test_<layer>/`).

## Extending the pipeline

- **New source**: add an entry to `config/pipeline_config.yaml`, a
  connector in `src/ingestion/` (registered in `registry.py`), and a
  canonical field-mapping entry in `src/orchestration/canonical_mapping.py`
  if it feeds `orders`/`shipments`.
- **New validation rule**: add it to the relevant canonical section
  (`orders`/`shipments`) in `config/quality_rules.yaml` — no code change
  needed, `rules_engine.py` reads the YAML directly.
- **New mart**: add a builder function to `src/transform/mart_builder.py`,
  register it in `build_all_marts()` and `MART_TABLES`/`SCOPE_TABLES` in
  `rebuild_marts_flow.py` if it should be rebuildable independently.
