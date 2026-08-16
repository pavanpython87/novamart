# Incremental Load Design

How NovaMart's pipeline guarantees that re-running it — on a schedule, or
by hand after a failure — never double-counts data. Idempotency is
enforced independently at three layers: file-level (don't re-read a file
you've already ingested), row-level (don't duplicate a row you've already
staged), and table-level (don't duplicate a fact you've already loaded).
No single layer is trusted alone.

## Layer 1: don't re-ingest a file — `IncrementalTracker`

`src/ingestion/incremental_tracker.py` wraps a single SQLite database
(`data/landing/novamart_tracker.db`) with two tables, used by two
different incremental strategies depending on the source:

**`file_registry`** — for every file-based source (CSV/Excel/JSON/XML/
flat-file: shopify, amazon, pos, shipping carriers, products), keyed on
`(source, file_path)`:

| Column | Purpose |
|---|---|
| `file_hash` | SHA-256 of the file's contents (`compute_file_hash`) |
| `row_count` | Rows extracted last time (0 for a file that failed to parse) |
| `processed_at` | Timestamp, updated on every re-check |

`IncrementalTracker.is_new_or_changed(source, file_path)` hashes the file
on disk and compares to the stored hash — `True` if the file has never
been seen for this source, or its content has changed since the hash was
recorded. `mark_processed` upserts (`ON CONFLICT ... DO UPDATE`) the new
hash after a successful extract. `_ingest_file_registry_source`
(`src/orchestration/tasks/ingest_tasks.py`) calls `is_new_or_changed`
before extracting and `mark_processed` after, so:

- Re-running the pipeline against an unchanged `data/incoming/` directory
  ingests **zero** rows the second time — every file's hash still matches.
- A file that's genuinely replaced (chaos-injected truncation, or a
  real corrected re-export) gets re-ingested, since its hash changed.
- Content-based hashing, not filename or mtime, is the identity — a file
  renamed-but-identical is correctly treated as already-seen; a file with
  the same name but different bytes is correctly treated as new.

**Malformed-file resilience**: `_ingest_file_registry_source` wraps the
extract call in a narrow except clause (`EXTRACT_ERRORS` —
`pd.errors.EmptyDataError`, `ParserError`, `ValueError` for JSON decode
errors, `OSError`, `zipfile.BadZipFile`, `lxml.etree.LxmlError`) covering
exactly the malformed-file outcomes the simulator's chaos injector
produces (emptied/truncated CSV or JSON, corrupted XLSX, broken XML). A
file that fails to parse is logged and marked processed with
`row_count=0` — this is deliberate: without it, a permanently corrupted
file would fail identically on every future run forever, since nothing
about `is_new_or_changed` would ever become `False` for it. Marking it
processed means it's tried exactly once and then skipped; if it's later
replaced with a valid file (different hash), it's picked up normally.
Critically, one bad file doesn't block the other files for that source
batch — extraction continues to the next file in the loop.

**`hwm_state`** — for query-based sources using `incremental_mode:
high_water_mark` (SQLite connectors), keyed on `(source, hwm_column)`,
storing a single scalar high-water-mark value (e.g. the max
`updated_at` seen so far). `_ingest_hwm_source` reads the stored HWM via
`get_hwm`, passes it to the connector so its query can filter to
`WHERE hwm_column > hwm_value`, then persists the connector's
`max_hwm_value` back via `set_hwm`. This avoids re-reading an entire
table on every run — only rows newer than the last run's watermark are
pulled.

Both tables use `INSERT ... ON CONFLICT DO UPDATE` upserts, so tracker
state itself never accumulates duplicate rows across runs.

## Layer 2: don't duplicate a staged order line — `_merge_stg_orders`

`stg_orders` (the canonical, cumulative order-line table every mart reads
from) is *not* upserted on a key — order-line identity isn't a single
clean primary key across all three channels. Instead,
`main_pipeline._merge_stg_orders` (`src/orchestration/flows/
main_pipeline.py`) does:

1. Read the entire existing `stg_orders` table from DuckDB (empty
   DataFrame if the table doesn't exist yet — first run).
2. Concatenate this run's freshly-built canonical `orders` DataFrame onto
   it.
3. Coerce numeric columns back to numeric dtype (`NUMERIC_ORDER_COLUMNS`)
   — a DuckDB round-trip through `fetchdf()` can silently widen an
   object-dtype column like `quantity` to `VARCHAR`, which would otherwise
   break `mart_builder`'s numeric aggregations once mixed with
   freshly-typed in-memory data from this run.
4. `combined.drop_duplicates(ignore_index=True)` — an **exact full-row**
   duplicate drop.

Because file-level dedup (Layer 1) already guarantees the same file is
never extracted twice, the only way `_merge_stg_orders` would see a
duplicate row is a full pipeline re-run over already-committed data (e.g.
a `backfill`/`full_refresh` re-run, or manual re-processing) — and an
exact-row duplicate is safe to drop unconditionally, since two genuinely
different order lines are vanishingly unlikely to match on every single
column (`order_id`, `product_key`, `gross_revenue`, `order_date`, all fee/
revenue fields, ...) by coincidence. This makes `stg_orders` idempotent
under re-runs without needing a synthetic composite key.

## Layer 3: don't duplicate a fact row — keyed upsert

Unlike `stg_orders`, the two star-schema fact tables that are actually
populated (`fact_shipments`, `fact_inventory_daily`) have an unambiguous
natural key, so they use `DuckDBLoader.upsert()`
(`src/load/duckdb_loader.py`) — a delete-then-insert keyed on
`schema_manager.PRIMARY_KEYS[table_name]`:

```sql
DELETE FROM {table} WHERE {key_col} IN (SELECT {key_col} FROM _incoming_df)
-- then
INSERT INTO {table} SELECT * FROM _incoming_df
```

- `fact_shipments` is keyed on `tracking_number` — re-processing the same
  tracking number (e.g. a shipment later marked delivered) replaces the
  row in place rather than adding a second one.
- `fact_inventory_daily` is keyed on `product_key` — each run's snapshot
  overwrites the previous one per product (see `docs/data_dictionary.md`
  for why this means it's a current-snapshot table, not a real daily
  history, today).

`dim_customers` additionally supports SCD Type 2 versioning
(`upsert_scd2_customers` — closes out the prior current row's
`valid_to`/`is_current` and inserts a new versioned row) via
`schema_manager.SCD2_TABLES`, though `dim_customers` itself isn't
currently populated by `main_pipeline` (see `docs/architecture.md`'s
"Data model: what's actually populated" section).

The five mart tables (`mart_revenue_daily`, etc.) don't need any of the
above — they're fully rebuilt every run via `CREATE OR REPLACE TABLE ...
AS SELECT * FROM _incoming_df` (`write_duckdb_tables`,
`src/orchestration/tasks/load_tasks.py`) directly from the now-cumulative
`stg_orders`, so they're always consistent with whatever `stg_orders`
currently contains — no incremental merge logic needed at that layer.

## Why three layers instead of one

Each layer protects against a different re-run scenario:

| Scenario | What would go wrong without... | ...this layer |
|---|---|---|
| Same `data/incoming/` re-processed unchanged | Every file re-parsed and re-appended every run — `stg_orders` grows without bound | `IncrementalTracker.file_registry` (skip unchanged files entirely) |
| `full_refresh`/`backfill` re-run over already-loaded date range | Exact same order lines appended a second time — revenue/mart numbers double | `_merge_stg_orders`'s exact-duplicate drop |
| Same shipment tracking number appears in two different daily shipping files (status update) | Two rows for one tracking number — `fact_shipments` no longer one-row-per-shipment | `DuckDBLoader.upsert`'s keyed delete-then-insert |

See `docs/architecture.md` for how these fit into the overall flow order,
and `docs/runbook.md` for which run mode (`daily`/`backfill`/
`full_refresh`/`incremental`) exercises which of these paths.
