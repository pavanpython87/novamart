# NovaMart — End-to-End Data Pipeline Portfolio Project

## Project plan and technical specification

---

## 1. Executive summary

**What this is:** A production-grade, continuously-running data pipeline that ingests messy multi-channel retail data from 6 sources, profiles and validates data quality, cleans and transforms 1M+ records through a layered warehouse architecture (SQLite → DuckDB → Google BigQuery), and delivers interactive business dashboards — with automated incremental loads, monitoring, and self-healing capabilities.

**Who it's for:** SMB clients on Upwork and freelance platforms who need someone to take their messy business data and turn it into reliable, automated reporting. This project is the proof.

**The business story:** NovaMart is a growing multi-channel retailer (~$4M annual revenue) selling consumer electronics and home goods across Shopify, Amazon Marketplace, and a physical retail store. They're drowning in disconnected data — 20+ hours per week spent manually reconciling orders, inventory, and financials. This pipeline eliminates that entirely.

**What makes this different from a tutorial project:**
- Data isn't static — a simulator generates new orders, returns, and shipments on a realistic schedule, mimicking real business activity
- The pipeline runs automatically via GitHub Actions — daily at 2 AM UTC, no local machine required. Your laptop can be off.
- Three-tier warehouse architecture — data physically moves between SQLite (landing), DuckDB (processing), and BigQuery (analytical serving)
- Containerized with Docker Compose — anyone can run the full stack with one command: `docker compose up`
- When things break, you can see it — quarantine, monitoring, drift detection, and alerting are built in
- The dashboard connects to a real cloud warehouse (BigQuery free tier), not a local file
- Idempotent by design — if a run fails, the next run catches up automatically. No data loss, no manual intervention.

---

## 2. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS DATA SIMULATION LAYER                         │
│                                                                             │
│  Simulates real business activity — new data arrives on a schedule          │
│                                                                             │
│  Every hour:    New POS transactions (JSON), ~25 orders                     │
│  Every 6 hours: Shopify order batch (CSV), ~150 orders                      │
│  Daily:         Amazon settlement (XLSX), ~500 orders + returns + fees      │
│  Daily:         Shipping carrier feeds (XML/CSV/TXT), ~250 shipments        │
│  Weekly:        Customer data sync (CSV), updated records                   │
│  Monthly:       Product catalog refresh (SQLite), new/updated products      │
│                                                                             │
│  Data includes realistic patterns:                                          │
│  - Seasonal sales spikes (Black Friday, holiday season)                     │
│  - Gradual data quality degradation (more nulls over time)                  │
│  - Occasional schema changes (new columns, renamed fields)                  │
│  - Random data anomalies (duplicate batches, corrupted files)               │
│  - New product launches, discontinued items                                 │
│  - Customer churn patterns                                                  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER (Python)                               │
│                                                                             │
│  Format-aware connectors with incremental extraction support:               │
│                                                                             │
│  - CSV reader: encoding detection, dialect sniffing, BOM handling           │
│  - Excel reader: multi-sheet, merged cells, formula error handling          │
│  - JSON reader: nested flattening, schema inference, malformed recovery     │
│  - XML parser: XPath extraction, namespace handling                         │
│  - SQLite connector: query-based extraction with change detection           │
│  - Flat file parser: fixed-width, pipe-delimited                            │
│                                                                             │
│  Incremental logic:                                                         │
│  - File-based sources: track last-processed file by name/timestamp          │
│  - Database sources: high-water mark on updated_at column                   │
│  - API sources: cursor/offset-based pagination                              │
│  - All modes: checksum comparison to skip already-processed files           │
│                                                                             │
│  Each ingestion produces: raw data + metadata envelope                      │
│  (row_count, file_hash, schema_fingerprint, extraction_timestamp)           │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               LOCAL LANDING ZONE — SQLite (novamart_landing.db)             │
│                                                                             │
│  Append-only. Original data preserved exactly as received.                  │
│  Every row tagged with _batch_id, _ingested_at, _source_file, _checksum    │
│                                                                             │
│  raw_shopify_orders          raw_products                                   │
│  raw_amazon_orders           raw_customers_shopify                          │
│  raw_amazon_returns          raw_customers_amazon                           │
│  raw_amazon_fees             raw_customers_pos                              │
│  raw_pos_transactions        raw_shipments_fedex                            │
│                              raw_shipments_ups                              │
│  _ingestion_log              raw_shipments_usps                             │
│  _file_registry (tracks      _batch_registry                               │
│   processed files)                                                          │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   PROFILING & QUALITY GATE LAYER                            │
│                                                                             │
│  Runs on every batch — compares current batch against historical baselines  │
│                                                                             │
│  Automated profiling (ydata-profiling):                                     │
│  - Row/column counts with delta from previous batch                        │
│  - Null % per column with threshold alerts                                  │
│  - Data type distribution shifts                                            │
│  - Value frequency anomalies (new categories, missing expected values)      │
│  - Statistical drift (KL divergence on numeric distributions)               │
│                                                                             │
│  Validation rules (Great Expectations):                                     │
│  - Business rules: amounts in range, dates not future, required fields     │
│  - Referential integrity: SKUs exist, customers exist, orders link         │
│  - Cross-field logic: qty × price ≈ subtotal (within rounding)             │
│  - Schema validation: expected columns present, types match                 │
│                                                                             │
│  Quality gate outcomes:                                                     │
│  PASS  → batch proceeds to staging                                          │
│  WARN  → batch proceeds + alert sent + quality trend logged                 │
│  FAIL  → entire batch quarantined + alert + pipeline continues              │
│          with other sources (one bad source doesn't block everything)        │
│                                                                             │
│  Schema drift detection:                                                    │
│  - New columns → log + alert (don't fail — new columns are common)          │
│  - Missing columns → FAIL (likely a broken export)                          │
│  - Type changes → WARN (investigate but don't block)                        │
│  - Null % spike > 20 points → WARN                                          │
│  - Row count drop > 50% → FAIL (likely truncated file)                      │
└────────────┬──────────────────────────────────────────┬─────────────────────┘
             │                                          │
             ▼                                          ▼
┌───────────────────────┐              ┌─────────────────────────────────────┐
│  QUARANTINE ZONE      │              │  LOCAL PROCESSING WAREHOUSE         │
│  SQLite               │              │  DuckDB (novamart_processing.duckdb)│
│  (novamart_quar.db)   │              │                                     │
│                       │              │  Staging tables (stg_):              │
│  quarantine_orders    │              │  - stg_orders_unified               │
│  quarantine_customers │              │  - stg_order_items                  │
│  quarantine_products  │              │  - stg_customers_resolved           │
│  quarantine_shipments │              │  - stg_products_mapped              │
│                       │              │  - stg_returns_linked               │
│  Each record has:     │              │  - stg_shipments_standardized       │
│  - original data      │              │                                     │
│  - quarantine_reason  │              │  Intermediate tables (int_):        │
│  - quarantine_rule    │              │  - int_revenue_decomposed           │
│  - quarantine_batch   │              │  - int_customer_metrics             │
│  - quarantine_ts      │              │  - int_inventory_snapshots          │
│  - review_status      │              │  - int_shipping_analytics           │
│                       │              │  - int_cohort_analysis              │
│  Supports:            │              │                                     │
│  - Manual review      │              │  Processing operations:             │
│  - Re-submission      │              │  - Phone/date/currency normalize    │
│  - Bulk resolution    │              │  - SKU mapping across channels      │
│                       │              │  - Fuzzy customer entity resolution │
└───────────────────────┘              │  - Order deduplication              │
                                       │  - Revenue & fee decomposition      │
                                       │  - CLV/churn/RFM scoring            │
                                       │  - Inventory velocity calculation   │
                                       │  - Time-series aggregation          │
                                       └──────────────┬──────────────────────┘
                                                      │
                                         Batch load (free) via
                                         google-cloud-bigquery Python client
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│          GOOGLE BIGQUERY — Cloud Analytical Warehouse (free tier)           │
│                                                                             │
│  Star schema — optimized for dashboard queries                              │
│  Tables partitioned by date for query cost control                          │
│  Mart tables built via BigQuery SQL (runs in BQ's engine, not locally)      │
│                                                                             │
│  FACT TABLES:                          DIMENSION TABLES:                    │
│  ┌────────────────────────┐            ┌────────────────────────┐          │
│  │ fact_orders             │            │ dim_customers           │          │
│  │ ──────────────────────  │            │ ────────────────────    │          │
│  │ order_key (SK)          │───────────▶│ customer_key (SK)      │          │
│  │ order_id (NK)           │            │ customer_id (NK)       │          │
│  │ customer_key (FK)       │            │ full_name              │          │
│  │ product_key (FK)        │            │ email                  │          │
│  │ date_key (FK)           │            │ phone_e164             │          │
│  │ channel_key (FK)        │            │ city, state, zip       │          │
│  │ quantity                │            │ first_order_date       │          │
│  │ unit_price              │            │ total_orders           │          │
│  │ gross_amount            │            │ lifetime_value         │          │
│  │ discount_amount         │            │ preferred_channel      │          │
│  │ platform_fee            │            │ churn_risk_score       │          │
│  │ payment_processing_fee  │            │ segment (high/med/low) │          │
│  │ net_revenue             │            │ _valid_from            │          │
│  │ cogs                    │            │ _valid_to              │          │
│  │ gross_profit            │            │ _is_current            │          │
│  │ shipping_cost           │            └────────────────────────┘          │
│  │ order_status            │                                                │
│  │ payment_method          │            ┌────────────────────────┐          │
│  │ _loaded_at              │            │ dim_products            │          │
│  │ _batch_id               │            │ ────────────────────    │          │
│  └────────────────────────┘            │ product_key (SK)       │          │
│                                         │ unified_sku            │          │
│  ┌────────────────────────┐            │ product_name           │          │
│  │ fact_returns            │            │ category / subcategory │          │
│  │ ──────────────────────  │            │ brand                  │          │
│  │ return_key (SK)         │            │ supplier               │          │
│  │ original_order_key (FK) │            │ unit_cost              │          │
│  │ product_key (FK)        │            │ is_active              │          │
│  │ return_date_key (FK)    │            └────────────────────────┘          │
│  │ return_reason           │                                                │
│  │ refund_amount           │            ┌────────────────────────┐          │
│  │ refund_type             │            │ dim_dates               │          │
│  │ restocking_fee          │            │ ────────────────────    │          │
│  └────────────────────────┘            │ date_key (PK)          │          │
│                                         │ full_date              │          │
│  ┌────────────────────────┐            │ day_of_week            │          │
│  │ fact_shipments          │            │ week_number            │          │
│  │ ──────────────────────  │            │ month_name             │          │
│  │ shipment_key (SK)       │            │ quarter                │          │
│  │ order_key (FK)          │            │ fiscal_year            │          │
│  │ carrier                 │            │ is_weekend             │          │
│  │ tracking_number         │            │ is_holiday             │          │
│  │ ship_date_key (FK)      │            │ season                 │          │
│  │ delivery_date_key (FK)  │            └────────────────────────┘          │
│  │ promised_days           │                                                │
│  │ actual_days             │            ┌────────────────────────┐          │
│  │ shipping_cost           │            │ dim_channels            │          │
│  │ delivery_status         │            │ ────────────────────    │          │
│  └────────────────────────┘            │ channel_key (PK)       │          │
│                                         │ channel_name           │          │
│  ┌────────────────────────┐            │ platform               │          │
│  │ fact_inventory_daily    │            │ fee_structure_json      │          │
│  │ ──────────────────────  │            │ avg_processing_fee_pct │          │
│  │ snapshot_date_key (FK)  │            └────────────────────────┘          │
│  │ product_key (FK)        │                                                │
│  │ channel_key (FK)        │                                                │
│  │ units_on_hand           │                                                │
│  │ units_reserved          │                                                │
│  │ days_of_inventory       │                                                │
│  │ reorder_flag            │                                                │
│  └────────────────────────┘                                                │
│                                                                             │
│  PRE-COMPUTED MART TABLES (built via BigQuery SQL, not Python):             │
│                                                                             │
│  mart_daily_channel_summary    — revenue, orders, AOV by day + channel      │
│  mart_weekly_product_perf      — sell-through, return rate by product       │
│  mart_monthly_customer_cohort  — retention curves by acquisition month      │
│  mart_quarterly_pnl            — full P&L waterfall by channel              │
│  mart_inventory_alerts         — reorder flags, dead stock, velocity        │
│                                                                             │
│  Free tier limits:  10 GB storage (we use ~0.5 GB)                          │
│                     1 TB queries/month (we use ~5 GB/month)                  │
│                     Batch loads are free (unlimited)                         │
│                                                                             │
│  Fallback: DuckDB serving layer (novamart_serving.duckdb) is always         │
│  populated in parallel — works offline without Google account               │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────────┐
                    │                         │
                    ▼                         ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│  EXPORT / DELIVERY LAYER │    │  REPORTING / DASHBOARD LAYER     │
│                          │    │  (Streamlit → BigQuery)           │
│  Automated on schedule:  │    │                                  │
│                          │    │  6 interactive dashboards:        │
│  Daily:                  │    │  1. Executive summary             │
│  - CSV to shared drive   │    │  2. Channel deep-dive             │
│  - Quality report HTML   │    │  3. Customer intelligence         │
│                          │    │  4. Inventory operations           │
│  Weekly:                 │    │  5. Shipping & fulfillment         │
│  - Excel report (CFO)   │    │  6. Pipeline health & monitoring  │
│  - Inventory alert email │    │                                  │
│                          │    │  Dashboard reads from BigQuery    │
│  Monthly:                │    │  (or DuckDB fallback) — cached   │
│  - PDF board summary     │    │  queries for sub-second response │
│  - Data quality trend    │    │                                  │
│    report                │    │  Auto-refreshes on pipeline run  │
└──────────────────────────┘    └──────────────────────────────────┘
```

---

## 3. Pipeline scheduling and incremental load design

This is the heart of what makes this a real pipeline, not a one-time script. Data arrives continuously, and the pipeline processes it incrementally.

### 3.1 Data simulation — continuous business activity

The data simulator generates new business activity on a realistic schedule, mimicking what a live business produces. This runs as a background process or scheduled task.

```
SIMULATION SCHEDULE:
────────────────────────────────────────────────────────────────────

Every hour (POS):
  └─ Generate 20-35 new retail transactions
  └─ Write to data/incoming/pos/pos_txn_YYYYMMDD_HHMM.json
  └─ Includes: ~5% cash, ~40% card, ~5% employee discounts
  └─ Weekends: 1.5x volume. Holidays: 2x volume.

Every 6 hours (Shopify):
  └─ Generate 100-200 new online orders
  └─ Write to data/incoming/shopify/shopify_batch_YYYYMMDD_HH.csv
  └─ Includes: ~3% with discount codes, ~8% international
  └─ Introduce data issues: ~2% duplicate rows, ~1% encoding problems

Daily at midnight (Amazon):
  └─ Generate 400-600 orders for the previous day
  └─ Write to data/incoming/amazon/amazon_daily_YYYYMMDD.xlsx
  └─ 4 sheets: Orders, Returns (~6% return rate), Fees, Adjustments
  └─ Introduce: merged cells in ~10% of files, formula errors in ~5%

Daily at 6 AM (Shipping):
  └─ Generate shipment records for orders fulfilled yesterday
  └─ FedEx: data/incoming/shipping/fedex_YYYYMMDD.xml
  └─ UPS: data/incoming/shipping/ups_YYYYMMDD.csv
  └─ USPS: data/incoming/shipping/usps_YYYYMMDD.txt
  └─ ~85% on-time delivery rate, ~3% lost/damaged

Weekly on Sunday (Customer sync):
  └─ Export updated customer records (new signups + profile changes)
  └─ data/incoming/customers/customer_sync_YYYYMMDD.csv
  └─ ~200-400 new customers per week, ~50 profile updates

Monthly on 1st (Product catalog):
  └─ Full catalog export with changes
  └─ data/incoming/products/catalog_YYYYMMDD.db
  └─ ~10-20 new products, ~5 discontinued, ~30 price changes

SEASONAL PATTERNS built into simulation:
  └─ Q4 (Oct-Dec): 2-3x order volume (holiday season)
  └─ January: spike in returns (post-holiday)
  └─ Prime Day (July): 2x Amazon orders
  └─ Back to school (Aug-Sep): 1.5x electronics
  └─ Weekday vs weekend volume differences
  └─ Gradual month-over-month growth (~3%)

DATA QUALITY DEGRADATION (simulated over time):
  └─ Month 6+: Shopify adds new column (discount_type) — schema drift
  └─ Month 9+: Amazon changes fee column names — breaking change
  └─ Month 12+: POS system upgrade changes JSON structure
  └─ Random months: duplicate file uploads (~2% chance per batch)
  └─ Random months: corrupted/truncated files (~1% chance)
  └─ Gradual increase in null rates for optional fields
```

### 3.2 Pipeline run modes

The pipeline supports multiple run modes, each appropriate for different situations:

```
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE RUN MODES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INCREMENTAL RUN (default, runs on schedule)                 │
│     ─────────────────────────────────────────                   │
│     Trigger: Scheduled (hourly/daily) or on new file arrival    │
│     Behavior:                                                   │
│     - Scans data/incoming/ for files not yet in _file_registry  │
│     - Ingests only new files (skips already-processed)          │
│     - Processes only new records through clean/transform        │
│     - Merges into existing warehouse tables (upsert)            │
│     - Rebuilds only affected mart tables                        │
│     Duration: 1-5 minutes for a typical daily batch             │
│                                                                 │
│  2. FULL REFRESH (manual or monthly maintenance)                │
│     ─────────────────────────────────────────                   │
│     Trigger: Manual or monthly schedule                         │
│     Behavior:                                                   │
│     - Truncates all staging + warehouse tables                  │
│     - Re-processes ALL files from data/incoming/                │
│     - Rebuilds entire star schema from scratch                  │
│     - Re-computes all metrics and mart tables                   │
│     - Reloads BigQuery (handles 60-day sandbox expiration)      │
│     Duration: 15-30 minutes for full 1M+ record reprocessing   │
│                                                                 │
│  3. SOURCE-SPECIFIC RUN (ad-hoc)                                │
│     ─────────────────────────────────────────                   │
│     Trigger: Manual, specific source name                       │
│     Behavior:                                                   │
│     - Re-ingests and reprocesses only the named source          │
│     - Useful when a source had issues and was fixed             │
│     Example: python run_pipeline.py --source amazon --reprocess │
│                                                                 │
│  4. BACKFILL RUN (historical)                                   │
│     ─────────────────────────────────────────                   │
│     Trigger: Manual, with date range                            │
│     Behavior:                                                   │
│     - Reprocesses files within a specific date range            │
│     - Useful when transformation logic was updated              │
│     Example: python run_pipeline.py --backfill 2024-01 2024-06  │
│                                                                 │
│  5. DRY RUN (testing)                                           │
│     ─────────────────────────────────────────                   │
│     Trigger: Manual                                             │
│     Behavior:                                                   │
│     - Ingests and profiles data but doesn't load to warehouse   │
│     - Generates quality reports without modifying anything      │
│     - Used to test new validation rules before deploying        │
│     Example: python run_pipeline.py --dry-run                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Incremental load mechanics

```
HOW INCREMENTAL DETECTION WORKS:
─────────────────────────────────

1. FILE REGISTRY (_file_registry table in SQLite landing)
   ┌──────────────────────────────────────────────────────────┐
   │ file_path           │ data/incoming/shopify/batch_01.csv │
   │ file_hash (SHA-256) │ a3f8c2...                         │
   │ file_size_bytes     │ 2,847,392                         │
   │ detected_at         │ 2024-03-15 02:00:00               │
   │ ingested_at         │ 2024-03-15 02:00:12               │
   │ row_count           │ 847                               │
   │ status              │ processed                         │
   │ batch_id            │ batch_20240315_020000              │
   │ schema_fingerprint  │ col1:str,col2:int,col3:date...    │
   └──────────────────────────────────────────────────────────┘

   On each run:
   a) Scan data/incoming/ recursively for all files
   b) Hash each file (SHA-256)
   c) Compare against _file_registry
   d) New file (path not in registry) → ingest
   e) Changed file (path exists, hash different) → re-ingest with warning
   f) Unchanged file (path + hash match) → skip
   g) Missing file (in registry, not on disk) → log warning

2. HIGH-WATER MARK (for database sources)
   ┌──────────────────────────────────────────────────────────┐
   │ source_name   │ product_catalog                         │
   │ table_name    │ products                                │
   │ hwm_column    │ updated_at                              │
   │ hwm_value     │ 2024-03-14 23:59:59                    │
   │ last_run      │ 2024-03-15 02:00:00                    │
   └──────────────────────────────────────────────────────────┘

   Query: SELECT * FROM products WHERE updated_at > {hwm_value}

3. WAREHOUSE UPSERT LOGIC
   - Fact tables: INSERT new records (natural key doesn't exist)
                  UPDATE if natural key exists and values changed
   - Dimensions: SCD Type 2 for customers (close old row, open new)
                 SCD Type 1 for products (overwrite in place)
   - Mart tables: Full rebuild of affected partitions only
                  (e.g., new orders today → rebuild today's mart row only)
```

### 3.4 Automated schedule (GitHub Actions — runs while your laptop is off)

The pipeline does NOT depend on your local machine being online. GitHub Actions runs everything on Microsoft's infrastructure — your laptop can be off, asleep, or on an airplane.

```
PIPELINE SCHEDULE (GitHub Actions cron):
──────────────────────────────────────────────────────────────────────

┌──────────────┬─────────────────────────┬────────────────────────────────┐
│ Schedule     │ GitHub Actions Workflow  │ What it does                   │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ Daily 2 AM   │ daily_pipeline.yml      │ 1. Simulate yesterday's data   │
│ UTC          │                         │    (new orders, returns, etc.) │
│              │                         │ 2. Run full incremental        │
│              │                         │    pipeline (ingest → load)    │
│              │                         │ 3. Load to BigQuery            │
│              │                         │ 4. Rebuild daily mart tables   │
│              │                         │ 5. Generate quality reports    │
│              │                         │ 6. Commit pipeline run log     │
│              │                         │    to repo (audit trail)       │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ Weekly Sun   │ weekly_rebuild.yml      │ 1. Rebuild weekly mart tables  │
│ 4 AM UTC     │                         │ 2. Recalculate customer        │
│              │                         │    segments, CLV, churn        │
│              │                         │ 3. Generate weekly Excel       │
│              │                         │    report (CFO export)         │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ Monthly 1st  │ monthly_refresh.yml     │ 1. Full pipeline refresh       │
│ 3 AM UTC     │                         │    (reprocess everything)      │
│              │                         │ 2. Reload all BigQuery tables  │
│              │                         │    (handles sandbox 60-day     │
│              │                         │    expiry)                     │
│              │                         │ 3. Generate monthly trend      │
│              │                         │    report + quality summary    │
│              │                         │ 4. Archive quarantine records  │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ On push      │ ci.yml                  │ Lint (ruff) + unit tests       │
│              │                         │ (pytest) + data validation     │
│              │                         │ checks                         │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ On merge     │ deploy_dashboard.yml    │ Deploy Streamlit dashboard     │
│ to main      │                         │ to Streamlit Cloud             │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ Manual       │ backfill.yml            │ Reprocess a date range         │
│ (workflow    │                         │ (input: start_date, end_date)  │
│ dispatch)    │                         │                                │
├──────────────┼─────────────────────────┼────────────────────────────────┤
│ Manual       │ full_refresh.yml        │ Nuclear option: regenerate     │
│              │                         │ all data, rebuild everything   │
└──────────────┴─────────────────────────┴────────────────────────────────┘

GitHub Actions free tier budget:
- Available: 2,000 minutes/month
- Daily pipeline (~5 min × 30): 150 min/month
- Weekly rebuild (~8 min × 4):   32 min/month
- Monthly refresh (~15 min × 1): 15 min/month
- CI on push (~2 min × ~30):     60 min/month
- Total: ~257 min/month — 13% of free tier
```

**Idempotent catch-up design:** If Monday's scheduled run fails (GitHub outage, BigQuery maintenance, transient error), Tuesday's run automatically processes both Monday's and Tuesday's data. The file registry tracks what's been processed, not when it was supposed to run. Three days of accumulated data produce the exact same warehouse state whether processed as three individual runs or one catch-up run. This is idempotency — the most important property of a production pipeline.

**Local development:** Prefect handles the DAG logic locally — task dependencies, retry, error handling, parallelism. Use it for development, testing, and manual runs. Same code, different trigger: GitHub Actions for scheduled production runs, Prefect for local development and debugging.

---

## 4. Data source specification

### 4.1 Shopify orders — CSV exports (350,000 historical + ongoing)

**Historical:** `shopify_orders_YYYY_MM.csv` (24 monthly files)
**Ongoing:** `shopify_batch_YYYYMMDD_HH.csv` (every 6 hours)

**Deliberate data issues:**
- Mixed date formats within the same file (MM/DD/YYYY vs YYYY-MM-DD)
- Currency symbols embedded in amount fields (`$49.99`, `CAD 12.50`, bare `49.99`)
- Unicode characters in customer names (accented names, CJK characters)
- ~2% duplicate rows from re-exports
- Blank rows between monthly data blocks
- Inconsistent column ordering between files (export template changes)
- Mixed case in status fields (`Paid`, `paid`, `PAID`, `Partially Paid`)
- Phone numbers in 6+ formats
- BOM characters in some files, mixed UTF-8 / Windows-1252 encoding
- **Month 6+:** New column `discount_type` appears (schema drift scenario)

### 4.2 Amazon marketplace — Excel workbooks (300,000 historical + ongoing)

**Historical:** `amazon_settlement_YYYY_MM.xlsx` (24 workbooks, 4 sheets each)
**Ongoing:** `amazon_daily_YYYYMMDD.xlsx` (daily)

**Sheet structure:** Orders, Returns, Fee Breakdown, Adjustments

**Deliberate data issues:**
- Merged header cells in ~10% of files
- Formula columns with `#REF!`, `#DIV/0!`, `#N/A` errors
- Mixed data types in the same column
- ASIN-to-SKU mapping inconsistencies
- Fee amounts with inconsistent sign conventions
- Date columns as Excel serial numbers in some sheets, text in others
- Sheet names varying between files (`Orders` vs `Order Data` vs `orders`)
- Amazon order IDs with leading zeros stripped by Excel
- **Month 9+:** Amazon renames `referral_fee` to `referral_fee_amount` (breaking change)

### 4.3 POS / retail — JSON API responses (200,000 historical + ongoing)

**Historical:** `pos_transactions_YYYY_MM_DD.json` (730 daily files)
**Ongoing:** `pos_txn_YYYYMMDD_HHMM.json` (hourly)

**Deliberate data issues:**
- Variable nesting depth, missing fields, `null` vs omitted
- Timestamps in local timezone without UTC offset
- Internal SKU format different from other channels
- Cash vs card payment structures differ
- Employee discounts in inconsistent locations
- ~40% of transactions have no loyalty ID
- Some daily files are empty (holidays)
- ~1% of files are malformed JSON (POS system crashes)
- **Month 12+:** POS system upgrade changes `items` array structure

### 4.4 Product catalog — SQLite database (5,000 products)

**File:** `novamart_products.db` (monthly full export)

**Deliberate data issues:**
- Duplicate products with name variations
- ~15% missing category assignments
- Weight in mixed units (lbs vs kg vs no unit)
- Discontinued products still marked active
- ~20% of products missing supplier cost (can't calculate margin)
- No cross-channel SKU mapping (must be built)

### 4.5 Customer data — mixed CSV and Excel (80,000 records)

**Historical:** 3 source files (Shopify CSV, Amazon XLSX, POS loyalty CSV)
**Ongoing:** `customer_sync_YYYYMMDD.csv` (weekly)

**Deliberate data issues (entity resolution challenge):**
- ~7,000 customers exist across 2+ sources with different identifiers
- Phone number format chaos (6+ formats)
- Name variations (`Bob` vs `Robert` vs `Robert J.`)
- Amazon has no phone, POS has no email
- ~3% intra-source duplicates
- Fake/test data (`test@test.com`, `John Doe`)

### 4.6 Shipping — XML/CSV/TXT (150,000 historical + ongoing)

**Historical:** FedEx quarterly XML, UPS monthly CSV, USPS monthly pipe-delimited
**Ongoing:** Daily files per carrier

**Deliberate data issues:**
- Three completely different schemas for the same entity
- Carrier-specific status codes (`DEL` vs `DELIVERED` vs `D`)
- Weight in lbs (FedEx), kg (UPS), oz (USPS)
- Date format differences (ISO vs MM/DD/YYYY vs YYYYMMDD)
- Tracking numbers in multiple files (carrier handoff)

---

## 5. Pipeline layer specification

### 5.1 Ingestion layer

```
src/
  ingestion/
    base_connector.py          # Abstract base: connect(), extract(), get_metadata()
    csv_connector.py           # Encoding detection, dialect sniffing, BOM handling
    excel_connector.py         # Multi-sheet, merged cells, formula handling
    json_connector.py          # Nested flattening, malformed recovery
    xml_connector.py           # XPath extraction, namespace handling
    sqlite_connector.py        # Query-based extraction with HWM
    flat_file_connector.py     # Fixed-width, pipe-delimited parsing
    file_watcher.py            # Scans incoming/, detects new/changed files
    registry.py                # Maps source configs → connectors
    incremental_tracker.py     # File registry + high-water mark management
```

### 5.2 Profiling and quality layer

```
src/
  profiling/
    profiler.py                # Core profiling engine (ydata-profiling wrapper)
    quality_scorecard.py       # Pass/warn/fail scoring with thresholds
    drift_detector.py          # Schema + distribution drift between batches
    baseline_manager.py        # Maintains statistical baselines per source
    report_generator.py        # HTML + JSON profiling reports
```

### 5.3 Validation layer

```
src/
  validation/
    rules_engine.py            # Rule definitions and evaluation
    expectations_suite.py      # Great Expectations integration
    quarantine_manager.py      # Failed record routing + reason codes
    validation_report.py       # Per-batch validation results
```

### 5.4 Cleaning and standardization

```
src/
  cleaning/
    phone_normalizer.py        # → E.164 format
    date_normalizer.py         # → ISO 8601 (handles 15+ input formats)
    currency_cleaner.py        # Strip symbols, handle locale decimals
    address_standardizer.py    # Abbreviations, casing, component parsing
    name_normalizer.py         # Trim, case, Unicode normalization
    sku_mapper.py              # Cross-channel SKU → unified product_id
    status_harmonizer.py       # Source-specific statuses → unified set
    unit_converter.py          # Weight: lbs/oz/kg → kg; Dims: in/cm → cm
```

### 5.5 Deduplication and entity resolution

```
src/
  dedup/
    customer_resolver.py       # Fuzzy matching across channels
    order_deduplicator.py      # Composite key + time window dedup
    product_matcher.py         # Name + brand + category similarity
    match_scorer.py            # Jaro-Winkler, Levenshtein, token set ratio
    merge_strategy.py          # Golden record construction
```

**Customer entity resolution:**
1. Exact match on email → confidence 0.95
2. Exact match on phone_e164 → confidence 0.90
3. Fuzzy: normalized name > 0.85 AND (partial address OR same zip) → confidence 0.75
4. Above 0.90 → auto-merge
5. 0.70 - 0.90 → flagged for review
6. Below 0.70 → separate customers
7. Golden record: most complete value per field, most recent wins ties

### 5.6 Transformation layer

```
src/
  transform/
    revenue_calculator.py      # Net revenue with full fee decomposition
    customer_analytics.py      # CLV, AOV, churn scoring, RFM, segmentation
    inventory_metrics.py       # Sell-through, reorder points, dead stock
    shipping_analytics.py      # Carrier performance, cost analysis
    time_series_builder.py     # Daily/weekly/monthly/quarterly aggregations
    cohort_builder.py          # Customer cohort analysis by acquisition month
    mart_builder.py            # Pre-computed aggregation tables
```

**Revenue decomposition (per order):**
```
  gross_revenue
  - platform_fees (Amazon: referral + FBA; Shopify: transaction fee)
  - payment_processing_fees (Stripe %, PayPal %, card terminal)
  - returns_and_refunds (partial vs full, restocking fees)
  - discounts_and_promotions (coupon, bulk, employee)
  ─────────────────────────────────────────────────────
  = net_revenue
  - COGS (product cost from supplier data)
  ─────────────────────────────────────────────────────
  = gross_profit per order per channel
```

### 5.7 Load layer

```
src/
  load/
    schema_manager.py          # DDL management for DuckDB + BigQuery
    duckdb_loader.py           # Local DuckDB upsert logic
    bigquery_loader.py         # BigQuery batch load via Python client
    export_manager.py          # Automated CSV, Excel, PDF generation
    partition_manager.py       # Date-based partitioning in BigQuery
    dual_loader.py             # Orchestrates loading to both destinations
```

**Dual-destination loading:**
- Every pipeline run loads to both DuckDB (always) and BigQuery (when configured)
- DuckDB serves as offline fallback and local development target
- BigQuery serves as the production analytical warehouse
- Streamlit reads from BigQuery by default, DuckDB as fallback
- Config toggle: `WAREHOUSE_BACKEND=bigquery|duckdb|both`

---

## 6. Orchestration and automation

### 6.1 Split responsibilities: GitHub Actions (scheduling) + Prefect (DAG logic)

```
GITHUB ACTIONS handles:                PREFECT handles:
─────────────────────────              ─────────────────────────
✓ Cron scheduling (daily/weekly/       ✓ Task dependency graph (DAG)
  monthly triggers)                    ✓ Parallel source ingestion
✓ Always-on execution (runs            ✓ Retry logic with exponential
  while your laptop is off)              backoff (3 attempts per task)
✓ Secret management (BigQuery          ✓ Error handling and recovery
  service account credentials)         ✓ Task-level logging and timing
✓ Pipeline run logging (commit         ✓ Local development and testing
  run summaries to repo)               ✓ Manual run modes (backfill,
✓ CI/CD (lint, test, deploy)             dry run, source-specific)
✓ Manual workflow dispatch             ✓ Flow orchestration within a
  (backfill with date inputs)            single pipeline run
```

### 6.2 GitHub Actions workflow files

```
.github/
  workflows/
    daily_pipeline.yml         # Cron: daily 2 AM UTC
    │                          # Steps:
    │                          #   1. Checkout repo
    │                          #   2. Set up Python + cache deps
    │                          #   3. Run simulator (yesterday's data)
    │                          #   4. Run pipeline (incremental mode)
    │                          #   5. Upload quality report as artifact
    │                          #   6. Commit run log to data/logs/ branch
    │
    weekly_rebuild.yml         # Cron: Sunday 4 AM UTC
    │                          # Steps: rebuild marts, recalc segments
    │
    monthly_refresh.yml        # Cron: 1st of month 3 AM UTC
    │                          # Steps: full refresh, reload BigQuery
    │
    ci.yml                     # Trigger: on push / on PR
    │                          # Steps: ruff lint, pytest, validation
    │
    deploy_dashboard.yml       # Trigger: merge to main
    │                          # Steps: deploy Streamlit to cloud
    │
    backfill.yml               # Trigger: manual (workflow_dispatch)
    │                          # Inputs: start_date, end_date
    │                          # Steps: reprocess date range
    │
    full_refresh.yml           # Trigger: manual (workflow_dispatch)
                               # Steps: regen all data, rebuild all
```

**Example: daily_pipeline.yml**
```yaml
name: Daily Pipeline
on:
  schedule:
    - cron: '0 2 * * *'       # 2:00 AM UTC every day
  workflow_dispatch:            # Allow manual trigger

jobs:
  pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Simulate yesterday's business data
        run: python scripts/simulate_new_data.py --date yesterday

      - name: Run incremental pipeline
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.BQ_SERVICE_ACCOUNT }}
          BQ_PROJECT_ID: ${{ secrets.BQ_PROJECT_ID }}
          WAREHOUSE_BACKEND: both    # Load to DuckDB + BigQuery
        run: python scripts/run_pipeline.py --mode incremental

      - name: Rebuild daily mart tables
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.BQ_SERVICE_ACCOUNT }}
        run: python scripts/run_pipeline.py --mode rebuild-marts --scope daily

      - name: Upload quality report
        uses: actions/upload-artifact@v4
        with:
          name: quality-report-${{ github.run_number }}
          path: data/profiling_reports/

      - name: Commit run log
        run: |
          git config user.name "Pipeline Bot"
          git config user.email "pipeline@novamart.dev"
          git add data/logs/
          git commit -m "Pipeline run $(date +%Y-%m-%d) [skip ci]" || true
          git push || true
```

### 6.3 Prefect flow structure (DAG logic)

```
src/
  orchestration/
    flows/
      main_pipeline.py          # Full end-to-end pipeline DAG
      incremental_flow.py       # Lightweight incremental run
      rebuild_marts_flow.py     # Mart table rebuild (daily/weekly scope)
      full_refresh_flow.py      # Full reprocessing from scratch
      backfill_flow.py          # Date-range reprocessing
      export_flow.py            # Report generation
    tasks/
      ingest_tasks.py           # Per-source ingestion (parallelized)
      profile_tasks.py          # Profiling + baseline comparison
      validate_tasks.py         # Quality gate + quarantine routing
      clean_tasks.py            # Normalization + standardization
      dedup_tasks.py            # Entity resolution + deduplication
      transform_tasks.py        # Business logic + metrics
      load_tasks.py             # Dual-destination loading
      simulate_tasks.py         # Data simulation wrappers
      notify_tasks.py           # Alert/notification tasks
    config.py                   # Pipeline configuration + env vars
```

**Error handling:**
- Each source ingests independently — one failure doesn't block others
- Quality gate failures quarantine bad records but don't halt pipeline
- Transformation errors logged with full context (input, rule, error)
- Retry logic: 3 attempts with exponential backoff for transient failures
- Pipeline always completes — partial results are better than no results
- Every run produces a summary: processed, quarantined, duration, errors
- GitHub Actions run logs preserved as artifacts for 90 days

### 6.2 Pipeline DAG (Directed Acyclic Graph)

```
┌──────────────────────┐
│ Trigger              │
│ (schedule / manual / │
│  file arrival)       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Scan for new data    │
│ (file watcher +      │
│  registry check)     │
└──────────┬───────────┘
           │
           ▼   (parallel ingestion — each source independent)
┌──────┬──────┬──────┬──────┬──────┬──────┐
│Shop. │Amaz. │ POS  │Prod. │Cust. │Ship. │
│CSV   │XLSX  │JSON  │SQLite│Mixed │XML   │
└──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┘
   └──────┴──────┴──────┴──────┴──────┘
                  │
                  ▼
       ┌──────────────────┐
       │ Profile + Validate│
       │ (per source)      │
       └────────┬─────────┘
                │
         PASS?──┤──FAIL?
          │     │    │
          │     │    ▼
          │     │  ┌──────────┐
          │     │  │Quarantine│
          │     │  └──────────┘
          ▼     ▼
  ┌────────────────────┐
  │ Clean + Standardize│
  └────────┬───────────┘
           │
  ┌────────▼───────────┐
  │ Deduplicate +      │
  │ Entity resolution  │
  └────────┬───────────┘
           │
  ┌────────▼───────────┐
  │ Transform +        │
  │ Business logic     │
  └────────┬───────────┘
           │
  ┌────────▼───────────┐
  │ Load (dual target) │
  │ DuckDB + BigQuery  │
  └────────┬───────────┘
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
┌──────┐┌──────┐┌──────┐┌─────────┐
│Build ││Export││Log   ││Refresh  │
│marts ││files ││run   ││dashboard│
│(BQ   ││      ││stats ││cache    │
│ SQL) ││      ││      ││         │
└──────┘└──────┘└──────┘└─────────┘
```

---

## 7. Monitoring and observability

### 7.1 Pipeline health metrics (tracked per run)

- Total records ingested per source (with delta from previous run)
- Records passed validation vs quarantined (with reason breakdown)
- Records deduplicated (with match confidence distribution)
- Transformation success/failure rates
- Records loaded to DuckDB and BigQuery
- Run duration (total and per-stage)
- BigQuery storage and query usage (free tier tracking)

### 7.2 Alert conditions

- Ingestion row count drops > 20% from previous run
- Null % for any critical column exceeds threshold
- Quarantine rate exceeds 5% for any source
- New values appear in categorical fields (data drift)
- Pipeline duration exceeds 2x average
- Schema change detected (new/missing/changed columns)
- BigQuery free tier usage exceeds 80% (storage or query)
- Any stage fails completely

### 7.3 Data quality trending

- Null percentage trends per column per source over time
- Duplicate rate trends per source
- Validation failure rates per rule over time
- Schema change history log
- Entity resolution match confidence distribution over time
- Quarantine resolution rate (how fast are quarantined records reviewed?)

---

## 8. Dashboard specification

### 8.1 Executive summary
Revenue scorecards (MTD, YTD, vs last year), channel performance bars, revenue trend with 7-day and 30-day moving averages, top/bottom 10 products, geographic revenue heat map.

### 8.2 Channel deep-dive
Revenue waterfall per channel (gross → fees → returns → net → COGS → profit), fee impact trending, cross-channel customer analysis, channel comparison table.

### 8.3 Customer intelligence
Customer segments (high-value, growing, at-risk, churned), cohort retention heatmap, CLV distribution, RFM scatter plot, churn risk table, acquisition channel analysis.

### 8.4 Inventory operations
Stock levels by category with reorder lines, reorder alerts with recommended quantities, dead stock list, sell-through rate by category and channel, seasonal demand patterns.

### 8.5 Shipping and fulfillment
Carrier performance comparison (speed, cost, damage rate), shipping cost as % of revenue trending, delivery time distribution, return rate by product/category/reason.

### 8.6 Pipeline health
Run history timeline with status and duration, data quality trends over time, source health per-source, quarantine review queue, schema change log, BigQuery usage tracker, processing throughput trends.

---

## 9. Project structure

```
novamart-data-pipeline/
│
├── README.md                          # Case study format with screenshots
├── LICENSE
├── requirements.txt
├── pyproject.toml
├── .env.example                       # BigQuery project ID, credentials path
│
├── ──── DOCKER ────
├── Dockerfile                         # Pipeline container (Python + all deps)
├── Dockerfile.dashboard               # Streamlit dashboard container
├── docker-compose.yml                 # Full stack: pipeline + dashboard + reports
├── docker-compose.dev.yml             # Development overrides (volume mounts, debug)
├── .dockerignore
│
├── ──── GITHUB ACTIONS ────
├── .github/
│   └── workflows/
│       ├── daily_pipeline.yml         # Cron: 2 AM UTC — simulate + pipeline + load
│       ├── weekly_rebuild.yml         # Cron: Sunday 4 AM — marts + segments
│       ├── monthly_refresh.yml        # Cron: 1st of month — full refresh + BQ reload
│       ├── ci.yml                     # On push: ruff lint + pytest + validation
│       ├── deploy_dashboard.yml       # On merge to main: deploy Streamlit
│       ├── backfill.yml               # Manual: workflow_dispatch with date inputs
│       └── full_refresh.yml           # Manual: regenerate everything from scratch
│
├── ──── CONFIG ────
├── config/
│   ├── pipeline_config.yaml           # Source definitions, thresholds, feature flags
│   ├── quality_rules.yaml             # Validation rule definitions per source
│   ├── sku_mapping.yaml               # Cross-channel SKU → unified product_id
│   ├── bigquery_schema.yaml           # BigQuery table definitions + partitioning
│   ├── simulator_config.yaml          # Data volumes, chaos levels, seasonal params
│   └── logging_config.yaml            # Log levels, output targets
│
├── ──── DATA (all gitignored except logs) ────
├── data/
│   ├── incoming/                      # Simulated source files arrive here
│   │   ├── shopify/                   # CSV batches (every 6 hours)
│   │   ├── amazon/                    # XLSX daily settlement files
│   │   ├── pos/                       # JSON hourly transaction dumps
│   │   ├── products/                  # SQLite monthly catalog exports
│   │   ├── customers/                 # Weekly sync CSVs
│   │   └── shipping/                  # XML/CSV/TXT daily carrier feeds
│   │
│   ├── landing/                       # SQLite: novamart_landing.db
│   ├── processing/                    # DuckDB: novamart_processing.duckdb
│   ├── serving/                       # DuckDB: novamart_serving.duckdb (fallback)
│   ├── quarantine/                    # SQLite: novamart_quarantine.db
│   ├── exports/                       # Generated CSV/Excel/PDF reports
│   ├── profiling_reports/             # HTML quality reports (served by nginx)
│   └── logs/                          # Pipeline run logs (committed to repo)
│       ├── run_history.jsonl          # Append-only run log
│       └── quality_trend.jsonl        # Quality metrics over time
│
├── ──── SOURCE CODE ────
├── src/
│   ├── __init__.py
│   │
│   ├── simulator/                     # Data generation engine
│   │   ├── __init__.py
│   │   ├── simulator_main.py          # Orchestrates all generators
│   │   ├── universe.py                # Shared product catalog, customer pool, pricing
│   │   ├── shopify_simulator.py       # CSV batches with Shopify-specific formatting
│   │   ├── amazon_simulator.py        # XLSX workbooks with multi-sheet structure
│   │   ├── pos_simulator.py           # Nested JSON with POS-specific quirks
│   │   ├── product_simulator.py       # Monthly catalog updates + new products
│   │   ├── customer_simulator.py      # Weekly syncs + cross-channel identity
│   │   ├── shipping_simulator.py      # Multi-carrier feeds (FedEx XML, UPS CSV, USPS TXT)
│   │   ├── seasonal_patterns.py       # Volume multipliers by date + day of week
│   │   ├── quality_degrader.py        # Progressive data issues over time
│   │   ├── chaos_injector.py          # Categorized issue injection (format, quality,
│   │   │                              #   schema, semantic, encoding)
│   │   └── fake_data_utils.py         # Realistic names, addresses, phone numbers,
│   │                                  #   product names, SKUs, ASINs
│   │
│   ├── ingestion/                     # Source-format-aware data extraction
│   │   ├── __init__.py
│   │   ├── base_connector.py          # Abstract base: connect(), extract(), metadata()
│   │   ├── csv_connector.py           # Encoding detection, dialect sniffing, BOM
│   │   ├── excel_connector.py         # Multi-sheet, merged cells, formula handling
│   │   ├── json_connector.py          # Nested flattening, malformed recovery
│   │   ├── xml_connector.py           # XPath extraction, namespace handling
│   │   ├── sqlite_connector.py        # Query-based extraction with HWM
│   │   ├── flat_file_connector.py     # Fixed-width, pipe-delimited parsing
│   │   ├── file_watcher.py            # Scans incoming/, detects new/changed files
│   │   ├── registry.py                # Maps source configs → connector classes
│   │   └── incremental_tracker.py     # File registry + high-water mark management
│   │
│   ├── profiling/                     # Data quality assessment
│   │   ├── __init__.py
│   │   ├── profiler.py                # Core profiling engine (ydata-profiling)
│   │   ├── quality_scorecard.py       # Pass/warn/fail scoring with thresholds
│   │   ├── drift_detector.py          # Schema + distribution drift between batches
│   │   ├── baseline_manager.py        # Maintains statistical baselines per source
│   │   └── report_generator.py        # HTML + JSON profiling reports
│   │
│   ├── validation/                    # Business rule enforcement
│   │   ├── __init__.py
│   │   ├── rules_engine.py            # Rule definitions and evaluation
│   │   ├── expectations_suite.py      # Great Expectations integration
│   │   ├── quarantine_manager.py      # Failed record routing + reason codes
│   │   └── validation_report.py       # Per-batch validation results
│   │
│   ├── cleaning/                      # Data standardization
│   │   ├── __init__.py
│   │   ├── phone_normalizer.py        # → E.164 format
│   │   ├── date_normalizer.py         # → ISO 8601 (handles 15+ input formats)
│   │   ├── currency_cleaner.py        # Strip symbols, handle locale decimals
│   │   ├── address_standardizer.py    # Abbreviations, casing, component parsing
│   │   ├── name_normalizer.py         # Trim, case, Unicode normalization
│   │   ├── sku_mapper.py              # Cross-channel SKU → unified product_id
│   │   ├── status_harmonizer.py       # Source-specific statuses → unified set
│   │   └── unit_converter.py          # Weight: lbs/oz/kg → kg; Dims: in/cm → cm
│   │
│   ├── dedup/                         # Entity resolution
│   │   ├── __init__.py
│   │   ├── customer_resolver.py       # Fuzzy matching across channels
│   │   ├── order_deduplicator.py      # Composite key + time window dedup
│   │   ├── product_matcher.py         # Name + brand + category similarity
│   │   ├── match_scorer.py            # Jaro-Winkler, Levenshtein, token set ratio
│   │   └── merge_strategy.py          # Golden record construction
│   │
│   ├── transform/                     # Business logic + analytics
│   │   ├── __init__.py
│   │   ├── revenue_calculator.py      # Net revenue with full fee decomposition
│   │   ├── customer_analytics.py      # CLV, AOV, churn, RFM, segmentation
│   │   ├── inventory_metrics.py       # Sell-through, reorder points, dead stock
│   │   ├── shipping_analytics.py      # Carrier performance, cost analysis
│   │   ├── time_series_builder.py     # Daily/weekly/monthly/quarterly rollups
│   │   ├── cohort_builder.py          # Customer cohort by acquisition month
│   │   └── mart_builder.py            # Pre-computed aggregation tables
│   │
│   ├── load/                          # Warehouse loading
│   │   ├── __init__.py
│   │   ├── schema_manager.py          # DDL management for DuckDB + BigQuery
│   │   ├── duckdb_loader.py           # Local DuckDB upsert logic
│   │   ├── bigquery_loader.py         # BigQuery batch load via Python client
│   │   ├── export_manager.py          # Automated CSV, Excel, PDF generation
│   │   ├── partition_manager.py       # Date-based partitioning in BigQuery
│   │   └── dual_loader.py            # Orchestrates loading to both destinations
│   │
│   ├── monitoring/                    # Pipeline observability
│   │   ├── __init__.py
│   │   ├── run_logger.py              # Pipeline run tracking (JSONL)
│   │   ├── quality_tracker.py         # Quality metric trending over time
│   │   ├── alert_manager.py           # Threshold-based alerting
│   │   ├── bigquery_usage_tracker.py  # Free tier usage watchdog
│   │   └── health_dashboard.py        # Streamlit page data provider
│   │
│   └── orchestration/                 # Pipeline DAG logic (Prefect)
│       ├── __init__.py
│       ├── flows/
│       │   ├── main_pipeline.py       # Full end-to-end pipeline DAG
│       │   ├── incremental_flow.py    # Lightweight incremental run
│       │   ├── rebuild_marts_flow.py  # Mart rebuild (daily/weekly scope)
│       │   ├── full_refresh_flow.py   # Full reprocessing from scratch
│       │   ├── backfill_flow.py       # Date-range reprocessing
│       │   └── export_flow.py         # Report generation
│       ├── tasks/
│       │   ├── ingest_tasks.py        # Per-source ingestion (parallelized)
│       │   ├── profile_tasks.py       # Profiling + baseline comparison
│       │   ├── validate_tasks.py      # Quality gate + quarantine routing
│       │   ├── clean_tasks.py         # Normalization + standardization
│       │   ├── dedup_tasks.py         # Entity resolution + deduplication
│       │   ├── transform_tasks.py     # Business logic + metrics
│       │   ├── load_tasks.py          # Dual-destination loading
│       │   ├── simulate_tasks.py      # Data simulation wrappers
│       │   └── notify_tasks.py        # Alert/notification tasks
│       └── config.py                  # Pipeline configuration + env vars
│
├── ──── DASHBOARD ────
├── dashboard/
│   ├── app.py                         # Streamlit main entry point
│   ├── pages/
│   │   ├── 1_executive_summary.py
│   │   ├── 2_channel_deep_dive.py
│   │   ├── 3_customer_intelligence.py
│   │   ├── 4_inventory_operations.py
│   │   ├── 5_shipping_operations.py
│   │   └── 6_pipeline_health.py
│   ├── components/
│   │   ├── charts.py                  # Reusable Plotly chart components
│   │   ├── filters.py                 # Date range, channel, category selectors
│   │   ├── scorecards.py              # KPI card components
│   │   └── db_connector.py            # BigQuery / DuckDB backend switcher
│   └── .streamlit/
│       └── config.toml                # Theme and layout config
│
├── ──── TESTS ────
├── tests/
│   ├── __init__.py
│   ├── test_simulator/
│   │   ├── test_shopify_simulator.py  # Verify CSV format, messiness injection
│   │   ├── test_amazon_simulator.py   # Verify XLSX structure, multi-sheet
│   │   └── test_chaos_injector.py     # Verify issue rates match config
│   ├── test_ingestion/
│   │   ├── test_csv_connector.py
│   │   ├── test_excel_connector.py
│   │   ├── test_json_connector.py
│   │   └── test_incremental_tracker.py
│   ├── test_cleaning/
│   │   ├── test_phone_normalizer.py
│   │   ├── test_date_normalizer.py
│   │   └── test_currency_cleaner.py
│   ├── test_dedup/
│   │   ├── test_customer_resolver.py
│   │   └── test_match_scorer.py
│   ├── test_transform/
│   │   ├── test_revenue_calculator.py
│   │   └── test_customer_analytics.py
│   ├── test_validation/
│   │   └── test_rules_engine.py
│   ├── test_load/
│   │   ├── test_duckdb_loader.py
│   │   └── test_bigquery_loader.py
│   ├── test_integration/
│   │   ├── test_incremental_pipeline.py   # Verify incremental load correctness
│   │   ├── test_full_refresh.py           # Verify full refresh idempotency
│   │   ├── test_schema_drift.py           # Verify drift handling
│   │   └── test_catchup.py               # Verify missed-run catch-up
│   └── fixtures/
│       ├── sample_shopify.csv
│       ├── sample_amazon.xlsx
│       ├── sample_pos.json
│       └── sample_fedex.xml
│
├── ──── DOCS ────
├── docs/
│   ├── architecture.md                # Full architecture with diagrams
│   ├── data_dictionary.md             # Every table, column, business rule
│   ├── data_simulator.md              # How source files are generated
│   ├── incremental_load_design.md     # Incremental + idempotent design
│   ├── runbook.md                     # How to run, troubleshoot, extend
│   ├── docker_guide.md                # Docker setup + development workflow
│   └── screenshots/                   # Dashboard screenshots for README
│
├── ──── SCRIPTS ────
├── scripts/
│   ├── generate_historical_data.py    # One-time: 2 years of historical data (1M+)
│   ├── simulate_new_data.py           # Ongoing: generate next day/week/month batch
│   ├── run_pipeline.py                # CLI: --mode incremental|full-refresh|backfill
│   │                                  #       --source shopify|amazon|pos|all
│   │                                  #       --dry-run
│   ├── setup_warehouse.py             # Initialize DuckDB + BigQuery schemas
│   ├── setup_bigquery.py              # BigQuery project/dataset setup helper
│   └── seed_demo.py                   # Quick demo: small data sample + pipeline
│
└── .gitignore
```

---

## 10. Technology stack (all free)

| Layer | Technology | Why | Cost |
|---|---|---|---|
| **Language** | Python 3.11+ | Universal in data engineering | Free |
| **Data processing** | pandas + polars | pandas for complex transforms, polars for performance on large datasets | Free |
| **Excel handling** | openpyxl | Reads merged cells, formulas, multi-sheet workbooks | Free |
| **XML parsing** | lxml | XPath support, namespace handling, performance | Free |
| **Data quality** | Great Expectations | Industry standard, generates HTML reports, extensible rule engine | Free |
| **Profiling** | ydata-profiling | One-line profiling reports with statistics and visualizations | Free |
| **Fuzzy matching** | rapidfuzz | Fast Jaro-Winkler, Levenshtein, token set ratio scoring | Free |
| **Phone normalization** | phonenumbers | Google's libphonenumber for Python — E.164 formatting | Free |
| **Local processing DB** | DuckDB | OLAP-optimized columnar DB, handles 1M+ rows instantly, zero infrastructure | Free |
| **Landing/quarantine DB** | SQLite | Built into Python, reliable for write-heavy operations, single file | Free |
| **Cloud warehouse** | Google BigQuery | Real cloud warehouse used by Fortune 500 companies, generous free tier | Free (10 GB / 1 TB) |
| **BigQuery client** | google-cloud-bigquery | Official Python SDK for batch loads and SQL execution | Free |
| **Scheduling** | GitHub Actions | Cron-based pipeline scheduling — runs on GitHub's infrastructure, not your laptop | Free (2,000 min/mo) |
| **DAG orchestration** | Prefect | Task dependency graphs, retry logic, parallel execution, local dev workflow | Free |
| **Containerization** | Docker + Docker Compose | Reproducible environment, one-command setup, matches CI exactly | Free |
| **Dashboard** | Streamlit | Interactive Python dashboards, free cloud hosting, connects to BigQuery | Free tier |
| **Charts** | Plotly | Interactive, publication-quality charts embedded in Streamlit | Free |
| **Version control** | GitHub | Clean repo, PR workflow, issue tracking | Free tier |
| **CI/CD** | GitHub Actions | Automated testing, linting, deployment on push/merge | Free tier |
| **Testing** | pytest | Standard Python testing with fixtures and parametrize | Free |
| **Linting** | ruff | Fast Python linter and formatter (replaces flake8 + black + isort) | Free |

---

## 11. Build plan

### Phase 1: Foundation + data simulator (days 1-4)

| Day | Task | Deliverable |
|---|---|---|
| 1 | Repo structure, config files, requirements.txt, .gitignore, Dockerfile skeleton | Clean repo on GitHub |
| 1 | Set up GitHub Actions CI workflow (ci.yml: ruff + pytest on push) | CI passing on every push |
| 1 | Build `fake_data_utils.py` — realistic names, addresses, phone numbers, product names | Utility module with tests |
| 2 | Build `universe.py` — shared product catalog (200 items), customer pool (5K identities), pricing rules, fee structures | Data universe that all sources draw from |
| 2 | Build `seasonal_patterns.py` — volume multipliers (Q4 spike, Prime Day, weekday/weekend), growth trends | Seasonal calendar for 2 years |
| 3 | Build `shopify_simulator.py` + `amazon_simulator.py` — source-specific formatting, column names, file structures | Shopify CSVs (350K) + Amazon XLSX (300K) |
| 3 | Build `pos_simulator.py` + `shipping_simulator.py` — JSON nesting, XML/CSV/TXT carrier formats | POS JSON (200K) + Shipping feeds (150K) |
| 4 | Build `product_simulator.py` + `customer_simulator.py` — SQLite catalog, cross-channel identity overlap | Product DB (5K) + Customer files (80K) |
| 4 | Build `chaos_injector.py` + `quality_degrader.py` — categorized issue injection (format, quality, schema, semantic, encoding) with progressive timeline | Configurable messiness engine |
| 4 | Build `simulator_main.py` — generates historical (2yr) or ongoing (next day/week/month) data with one command | `python scripts/generate_historical_data.py` produces 1.08M records |

### Phase 2: Ingestion + incremental tracking (days 5-7)

| Day | Task | Deliverable |
|---|---|---|
| 5 | Build `BaseConnector` + `csv_connector.py` (encoding detection, BOM, dialect) + `excel_connector.py` (merged cells, formulas, multi-sheet) | Shopify + Amazon ingested to raw landing |
| 5 | Build `json_connector.py` (nested flattening, malformed recovery) + `xml_connector.py` (XPath, namespaces) | POS + FedEx XML ingested |
| 6 | Build `sqlite_connector.py` + `flat_file_connector.py` (pipe-delimited) | All 6 sources ingested |
| 6 | Build `file_watcher.py` + `incremental_tracker.py` (file registry with SHA-256, high-water mark) | Incremental detection working — skips already-processed files |
| 7 | Build profiling engine (`profiler.py` + `baseline_manager.py`) with ydata-profiling integration | HTML profiling reports per source per batch |
| 7 | Build `drift_detector.py` + `quality_scorecard.py` (pass/warn/fail with configurable thresholds) | Schema drift alerts + quality gates |

### Phase 3: Validation + cleaning + dedup (days 8-10)

| Day | Task | Deliverable |
|---|---|---|
| 8 | Build Great Expectations validation suite + `quarantine_manager.py` (routes failed records with reason codes) | Business rule validation + quarantine working |
| 8 | Build normalizers: `phone_normalizer.py` (E.164), `date_normalizer.py` (15+ formats → ISO 8601), `currency_cleaner.py` | Core field standardization |
| 9 | Build `address_standardizer.py`, `name_normalizer.py`, `status_harmonizer.py`, `unit_converter.py` | All cleaning rules implemented |
| 9 | Build `sku_mapper.py` — cross-channel SKU resolution (Shopify SKU ↔ Amazon ASIN ↔ POS internal_sku → unified product_id) | Cross-channel product identity |
| 10 | Build `customer_resolver.py` + `match_scorer.py` — fuzzy matching (email exact → phone exact → name+address fuzzy) with confidence scores | Entity resolution across 80K customers |
| 10 | Build `order_deduplicator.py` + `product_matcher.py` + `merge_strategy.py` (golden record construction) | Deduplicated staging tables |

### Phase 4: Transform + load (days 11-14)

| Day | Task | Deliverable |
|---|---|---|
| 11 | Build `revenue_calculator.py` — full fee decomposition (platform fees, payment fees, returns, discounts → net revenue → COGS → gross profit per order per channel) | Revenue metrics per order |
| 11 | Build `customer_analytics.py` — CLV, AOV, purchase frequency, churn risk scoring, RFM segmentation | Customer dimension enriched |
| 12 | Build `inventory_metrics.py` (sell-through, reorder points, dead stock) + `shipping_analytics.py` (carrier performance, cost analysis) | Inventory + shipping insights |
| 12 | Build `time_series_builder.py` (daily/weekly/monthly/quarterly rollups) + `cohort_builder.py` (retention curves) | Temporal analysis tables |
| 13 | Build `schema_manager.py` + `duckdb_loader.py` — DuckDB star schema with upsert logic (SCD Type 2 for customers) | Local warehouse populated |
| 13 | Set up BigQuery project + build `bigquery_loader.py` — batch loads via `google-cloud-bigquery` client + `partition_manager.py` | BigQuery schema created + data loaded |
| 14 | Build `dual_loader.py` (loads to DuckDB + BigQuery in parallel) + `mart_builder.py` (mart SQL runs in BigQuery's engine) | Both warehouses populated with 5 mart tables |

### Phase 5: Orchestration + monitoring + Docker (days 15-18)

| Day | Task | Deliverable |
|---|---|---|
| 15 | Build Prefect flows: `main_pipeline.py` (full DAG), `incremental_flow.py`, `full_refresh_flow.py` | Pipeline DAG with parallel ingestion, retry logic |
| 15 | Build `rebuild_marts_flow.py` + `backfill_flow.py` + `export_flow.py` | All run modes operational |
| 16 | Build `run_logger.py` (JSONL append-only log) + `quality_tracker.py` (metrics trending) + `alert_manager.py` | Monitoring operational |
| 16 | Build `bigquery_usage_tracker.py` (free tier watchdog) + `export_manager.py` (automated CSV/Excel/PDF) | Usage alerts + scheduled exports |
| 17 | Build `Dockerfile` (pipeline container) + `Dockerfile.dashboard` (Streamlit container) | Pipeline and dashboard containerized |
| 17 | Build `docker-compose.yml` (pipeline + dashboard + nginx for reports) + `docker-compose.dev.yml` (dev overrides) | `docker compose up` runs full stack |
| 18 | Build GitHub Actions workflows: `daily_pipeline.yml`, `weekly_rebuild.yml`, `monthly_refresh.yml` | Automated scheduled runs on GitHub's infrastructure |
| 18 | Integration test: simulate 7 days of data, run pipeline daily, verify idempotent catch-up | Full lifecycle verified end-to-end |

### Phase 6: Dashboards (days 19-22)

| Day | Task | Deliverable |
|---|---|---|
| 19 | Streamlit app skeleton + `db_connector.py` (BigQuery/DuckDB backend switcher) + global filters | App framework running |
| 19 | Executive summary dashboard (scorecards, trends, top/bottom products, geo map) | Dashboard 1 complete |
| 20 | Channel deep-dive dashboard (revenue waterfall, fee analysis, cross-channel customers) | Dashboard 2 complete |
| 20 | Customer intelligence dashboard (cohorts, CLV distribution, RFM, churn risk) | Dashboard 3 complete |
| 21 | Inventory operations dashboard (stock levels, reorder alerts, dead stock, seasonal demand) | Dashboard 4 complete |
| 21 | Shipping operations dashboard (carrier comparison, delivery times, return analysis) | Dashboard 5 complete |
| 22 | Pipeline health dashboard (run history, quality trends, quarantine queue, BQ usage, schema log) | Dashboard 6 complete |

### Phase 7: Polish + deploy (days 23-25)

| Day | Task | Deliverable |
|---|---|---|
| 23 | Deploy Streamlit to Streamlit Cloud (connected to BigQuery) | Live demo URL |
| 23 | Verify GitHub Actions daily pipeline runs end-to-end (simulate → pipeline → BigQuery → dashboard) | Automated pipeline confirmed working |
| 24 | Write case-study README with screenshots + architecture diagram | Professional README |
| 24 | Write docs: `architecture.md`, `data_dictionary.md`, `data_simulator.md`, `docker_guide.md` | Complete documentation |
| 25 | Record 2-minute Loom walkthrough (pipeline run → dashboard → pipeline health) | Video link in README |
| 25 | Final: code review, test coverage check, CI green, edge cases, `runbook.md` | Production-quality, portfolio-ready codebase |

---

## 12. Docker Compose design

### 12.1 Why Docker (and why not Kubernetes)

Docker Compose is the right level of containerization for this project. It solves a real problem: anyone can clone the repo and run the full stack with one command (`docker compose up`) — no Python version issues, no dependency conflicts, no BigQuery setup required for local testing.

Kubernetes would be overengineering. K8s solves infrastructure scaling problems — running multiple containers, auto-scaling, service discovery. Our pipeline is a single Python process that runs for 5 minutes once a day. There's nothing to scale, nothing to distribute. Adding K8s here would signal "I added buzzwords" rather than "I chose the right tool." The ability to explain why K8s doesn't fit here is itself a sign of engineering maturity.

### 12.2 Container architecture

```
docker-compose.yml
──────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────┐
│  SERVICE: pipeline                                       │
│                                                          │
│  Image: Dockerfile (Python 3.11-slim)                    │
│  Purpose: Run data simulator + pipeline                  │
│  Volumes:                                                │
│    - ./data:/app/data        (persist databases)         │
│    - ./config:/app/config    (pipeline configuration)    │
│  Environment:                                            │
│    - WAREHOUSE_BACKEND=duckdb (default, no BQ needed)    │
│    - BQ_PROJECT_ID (optional, for BigQuery mode)         │
│  Command: python scripts/run_pipeline.py --mode <mode>   │
│  Networks: novamart-net                                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  SERVICE: dashboard                                      │
│                                                          │
│  Image: Dockerfile.dashboard (Python 3.11-slim)          │
│  Purpose: Serve Streamlit dashboard                      │
│  Ports: 8501:8501                                        │
│  Volumes:                                                │
│    - ./data/serving:/app/data/serving   (read-only)      │
│  Depends on: pipeline (waits for first run)              │
│  Healthcheck: curl localhost:8501/_stcore/health          │
│  Networks: novamart-net                                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  SERVICE: quality-reports                                │
│                                                          │
│  Image: nginx:alpine                                     │
│  Purpose: Serve HTML profiling reports                   │
│  Ports: 8080:80                                          │
│  Volumes:                                                │
│    - ./data/profiling_reports:/usr/share/nginx/html (RO) │
│  Networks: novamart-net                                  │
└─────────────────────────────────────────────────────────┘
```

### 12.3 Usage

```bash
# Full stack — generate data, run pipeline, start dashboard
docker compose up

# Just the pipeline (no dashboard)
docker compose run pipeline python scripts/run_pipeline.py --mode incremental

# Generate historical data first, then run pipeline
docker compose run pipeline python scripts/generate_historical_data.py
docker compose run pipeline python scripts/run_pipeline.py --mode full-refresh

# Development mode (live code reload, debug logging)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests inside the container
docker compose run pipeline pytest tests/ -v
```

### 12.4 Dockerfile design

```dockerfile
# Dockerfile (pipeline)
FROM python:3.11-slim

WORKDIR /app

# System deps for lxml, openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY dashboard/ dashboard/

# Default: run the daily pipeline
CMD ["python", "scripts/run_pipeline.py", "--mode", "incremental"]
```

---

## 13. Data simulator detailed design

### 13.1 Architecture: layered generation

The simulator doesn't generate random data with random problems. It uses a four-layer approach that mirrors how real business data gets created and corrupted:

```
LAYER 1: SHARED UNIVERSE (universe.py)
──────────────────────────────────────
A single source of truth that all generators draw from:
- Product catalog: ~200 items across 8 categories (Audio, Computing,
  Home & Kitchen, Cameras, Gaming, Wearables, Accessories, Seasonal)
  Each product has: name, brand, category, cost, retail price, weight,
  dimensions, Shopify SKU, Amazon ASIN, POS internal_sku
- Customer pool: ~5,000 identities with realistic names (including
  international names with accents/Unicode), addresses across US + CA,
  emails (personal + work), phone numbers, loyalty IDs
- Cross-channel overlap: ~1,400 customers (28%) exist across 2+ channels
  with different identifiers (different emails, name variations,
  different phone formats)
- Pricing rules: Amazon referral fees by category (8-15%), FBA fees by
  weight/size tier, Shopify transaction fees (2.9% + $0.30), POS
  terminal fees (2.6% + $0.10)
- Return rates: 6% Amazon, 4% Shopify, 2% POS (with reason code
  distribution)

LAYER 2: TEMPORAL PATTERNS (seasonal_patterns.py)
─────────────────────────────────────────────────
- Base daily volume: Shopify 50, Amazon 40, POS 25 orders
- Day-of-week: weekdays 1.0x, Saturday 1.3x, Sunday 1.1x
- Monthly growth: 3% month-over-month compound
- Seasonal multipliers:
  - Q4 holiday (Nov-Dec): 2.5x
  - Black Friday / Cyber Monday: 4x (single weekend)
  - Prime Day (July): 2x Amazon only
  - Back to school (Aug-Sep): 1.5x electronics
  - January clearance: 0.8x orders, 1.8x returns
  - Summer lull (Jun-Jul): 0.85x
- Product seasonality: heaters spike in winter, fans in summer,
  gift items in December

LAYER 3: SOURCE-SPECIFIC FORMATTING
────────────────────────────────────
Each channel's data gets reformatted to match what that real system
actually exports:

Shopify → CSV with Shopify's column names, date formats, status values
Amazon  → XLSX with 4-sheet structure, Amazon fee columns, ASIN format
POS     → Nested JSON with the specific structure of Square/Toast APIs
FedEx   → XML with namespaces and FedEx-specific tracking format
UPS     → CSV with no header row, UPS tracking number format (1Z...)
USPS    → Pipe-delimited fixed-width with USPS status codes

LAYER 4: CHAOS INJECTION (chaos_injector.py + quality_degrader.py)
──────────────────────────────────────────────────────────────────
Controlled injection of categorized data issues at configurable rates.
Rates increase over time to simulate real-world quality degradation.
```

### 13.2 Issue categories and injection rates

Each data issue falls into one of five categories. Each category tests a different pipeline capability:

```
CATEGORY: FORMAT ISSUES
───────────────────────
Tests: ingestion layer's ability to handle format variations
Issues:
  - Mixed date formats (MM/DD/YYYY vs YYYY-MM-DD in same file) — 15%
  - Currency symbols in amount fields ($49.99 vs 49.99) — 20%
  - Phone numbers in 6+ formats — 100% (always varied)
  - Excel serial numbers instead of dates — 10% of XLSX sheets
  - Pipe-delimited field overflow (value wider than fixed width) — 5%
  - XML namespace variations between FedEx quarterly files — 2 variants

CATEGORY: DATA QUALITY
──────────────────────
Tests: validation + quarantine pipeline
Issues:
  - Duplicate rows (re-export artifacts) — 2% of Shopify CSVs
  - Blank/empty rows between sections — 1-3 per Shopify file
  - Trailing whitespace in string fields — 10%
  - Mixed case in status fields (Paid/paid/PAID) — 30%
  - Null values in required fields — 3% (should quarantine)
  - Formula errors in Excel (#REF!, #DIV/0!) — 5% of XLSX files
  - Malformed JSON (truncated files) — 1% of POS files
  - Negative amounts where positive expected — 0.5% (quarantine)
  - Future dates — 0.3% (quarantine)
  - Test/fake data (test@test.com, John Doe at 123 Main St) — 1%
  - Missing category assignments in product catalog — 15%
  - Null supplier costs (can't calculate margin) — 20% of products

CATEGORY: SCHEMA DRIFT
───────────────────────
Tests: drift detection + adaptive ingestion
Issues:
  - Month 6: Shopify adds new column "discount_type"
  - Month 9: Amazon renames "referral_fee" → "referral_fee_amount"
  - Month 12: POS JSON changes items array nesting structure
  - Inconsistent column ordering between files — 2 Shopify variants
  - Sheet name variations in Excel (Orders vs Order Data) — 3 variants
  - Extra sheets in some Excel files (pivot tables) — 5% of XLSX

CATEGORY: SEMANTIC CONFLICTS
─────────────────────────────
Tests: cross-channel resolution + business logic
Issues:
  - Same customer with different names across channels (Bob vs Robert)
  - Same customer with different emails across channels (personal vs work)
  - Same product with different identifiers (SKU vs ASIN vs internal_sku)
  - ASIN-to-SKU mapping inconsistencies across months
  - Fee amounts with inconsistent sign conventions (+ vs -) — 30% of Amazon
  - Employee discounts in inconsistent JSON locations — 2 patterns
  - Carrier-specific status codes (DEL vs DELIVERED vs D vs 301)
  - Weight in different units by carrier (lbs vs kg vs oz)
  - Date formats by carrier (ISO vs MM/DD vs YYYYMMDD)
  - Carrier handoff duplicates (same shipment in FedEx + USPS) — 5%

CATEGORY: ENCODING PROBLEMS
────────────────────────────
Tests: ingestion layer's character encoding handling
Issues:
  - BOM characters in CSV headers — 10% of Shopify files
  - Windows-1252 encoding instead of UTF-8 — 5% of Shopify files
  - HTML entities in product names (&amp; &#39;) — 3%
  - Unicode characters in customer names (accented, CJK) — 8%
  - Invisible characters (zero-width spaces, non-breaking spaces) — 2%
```

### 13.3 Quality degradation timeline

The simulator doesn't just inject random issues — quality degrades progressively over the 2-year dataset, simulating how real business data evolves:

```
Month 1-5:   BASELINE
             Standard issue rates as defined above.
             Pipeline should handle these cleanly.
             All quality gates pass.

Month 6:     SCHEMA DRIFT (Shopify)
             Shopify export template changes — new column "discount_type"
             appears. Pipeline must: detect new column → log drift alert →
             continue processing (new columns are common, shouldn't fail).

Month 7-8:   GRADUAL QUALITY DECLINE
             Null rates increase in optional fields:
             - phone: 5% → 12%
             - notes: 40% → 55%
             - shipping_address_line_2: 30% → 45%
             Drift detector should flag the trend in quality reports.

Month 9:     BREAKING SCHEMA CHANGE (Amazon)
             Amazon renames "referral_fee" to "referral_fee_amount".
             Pipeline must: detect missing expected column → detect new
             unknown column → map old → new (or fail gracefully and
             quarantine the batch with a clear error message).

Month 10-11: DUPLICATE FILE UPLOADS
             ~2% chance per batch of the same file being uploaded twice
             (different filename, same content). Pipeline must: detect
             via SHA-256 checksum → skip duplicate → log warning.

Month 12:    SYSTEM UPGRADE (POS)
             POS system upgrades from v3 to v4. JSON structure changes:
             - "items" array moves from transaction root to nested
               "line_items" object
             - "payment.card_type" becomes "payment.instrument.type"
             Pipeline must: handle both old and new formats simultaneously
             (some days have v3, some v4, transition period has both).

Month 13-18: INCREASING CHAOS
             - Occasional corrupted files (truncated mid-write) — 1%
             - Occasional empty files (system error) — 0.5%
             - More duplicate rows in Shopify (new staff doing exports)
             - Higher return rates in Q4 (holiday season returns)
             Pipeline must: quarantine bad files, alert, continue with
             other sources. Never crash. Always produce partial results.

Month 19-24: STABILIZATION
             Quality issues plateau. Pipeline has adapted to all schema
             changes. This period demonstrates that monitoring correctly
             shows quality stabilizing after the turbulent middle period.
```

### 13.4 Simulator commands

```bash
# Generate 2 years of historical data (1.08M records)
python scripts/generate_historical_data.py
  --start-date 2024-01-01
  --end-date 2025-12-31
  --output-dir data/incoming/

# Generate next day of ongoing data (called by GitHub Actions daily)
python scripts/simulate_new_data.py
  --date yesterday                     # or --date 2026-01-15
  --output-dir data/incoming/

# Generate a specific date range (for backfill testing)
python scripts/simulate_new_data.py
  --start-date 2025-06-01
  --end-date 2025-06-30
  --output-dir data/incoming/

# Generate with custom chaos level (for testing)
python scripts/simulate_new_data.py
  --date yesterday
  --chaos-level 0.8                    # 80% chaos (extreme testing)
  --output-dir data/incoming/

# Generate with specific issue category only (for targeted testing)
python scripts/simulate_new_data.py
  --date yesterday
  --issues schema_drift,encoding       # Only these categories
  --output-dir data/incoming/
```

---

## 14. GitHub Actions detailed design

### 14.1 How the automated daily pipeline works

This is the sequence that runs every night at 2 AM UTC without your laptop being on:

```
┌─────────────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS: daily_pipeline.yml                              │
│ Trigger: cron 0 2 * * * (2:00 AM UTC daily)                    │
│ Runner: ubuntu-latest (GitHub's infrastructure)                 │
│ Timeout: 20 minutes                                             │
│ Cost: ~5 min/run × 30 days = 150 min/month (of 2,000 free)     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
    Step 1: Checkout repo         ▼
    ┌──────────────────────────────────┐
    │ actions/checkout@v4              │
    │ Gets latest code + data/logs/   │
    └──────────────────┬───────────────┘
                       │
    Step 2: Setup      ▼
    ┌──────────────────────────────────┐
    │ Python 3.11 + pip cache         │
    │ pip install -r requirements.txt  │
    └──────────────────┬───────────────┘
                       │
    Step 3: Simulate   ▼
    ┌──────────────────────────────────┐
    │ python scripts/simulate_new_    │
    │   data.py --date yesterday      │
    │                                  │
    │ Generates: Shopify CSVs,        │
    │ Amazon XLSX, POS JSON, shipping │
    │ feeds for yesterday's date.     │
    │ Files land in data/incoming/    │
    └──────────────────┬───────────────┘
                       │
    Step 4: Pipeline   ▼
    ┌──────────────────────────────────┐
    │ python scripts/run_pipeline.py  │
    │   --mode incremental            │
    │                                  │
    │ env:                             │
    │   GOOGLE_APPLICATION_CREDENTIALS │
    │   = ${{ secrets.BQ_SA_KEY }}     │
    │   BQ_PROJECT_ID                  │
    │   = ${{ secrets.BQ_PROJECT }}    │
    │   WAREHOUSE_BACKEND=both         │
    │                                  │
    │ Runs: ingest → profile →        │
    │ validate → clean → dedup →      │
    │ transform → load (DuckDB + BQ)  │
    └──────────────────┬───────────────┘
                       │
    Step 5: Marts      ▼
    ┌──────────────────────────────────┐
    │ python scripts/run_pipeline.py  │
    │   --mode rebuild-marts          │
    │   --scope daily                 │
    │                                  │
    │ Rebuilds today's partition in   │
    │ mart tables via BigQuery SQL    │
    └──────────────────┬───────────────┘
                       │
    Step 6: Artifacts  ▼
    ┌──────────────────────────────────┐
    │ Upload quality report as        │
    │ GitHub Actions artifact          │
    │ (viewable in Actions UI for     │
    │ 90 days)                         │
    └──────────────────┬───────────────┘
                       │
    Step 7: Commit log ▼
    ┌──────────────────────────────────┐
    │ git add data/logs/              │
    │ git commit -m "Pipeline run     │
    │   2026-01-15 [skip ci]"         │
    │ git push                         │
    │                                  │
    │ Run summary (JSONL) committed   │
    │ to repo — creates audit trail   │
    │ visible in git history          │
    └──────────────────────────────────┘
```

### 14.2 Secrets management

```
GitHub Repository Settings → Secrets and variables → Actions:

BQ_SA_KEY         # Base64-encoded BigQuery service account JSON
BQ_PROJECT_ID     # Google Cloud project ID (e.g., novamart-pipeline)

The daily_pipeline.yml decodes BQ_SA_KEY to a temp file:
  echo "${{ secrets.BQ_SA_KEY }}" | base64 -d > /tmp/bq-key.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/bq-key.json

No secrets needed for DuckDB-only mode — set WAREHOUSE_BACKEND=duckdb
to skip BigQuery entirely (useful for fork-and-run demos).
```

### 14.3 Free tier budget tracking

```
GitHub Actions free tier: 2,000 minutes/month

Our usage:
  daily_pipeline.yml:     ~5 min × 30 = 150 min/month
  weekly_rebuild.yml:     ~8 min × 4  =  32 min/month
  monthly_refresh.yml:   ~15 min × 1  =  15 min/month
  ci.yml (on push):       ~2 min × 30 =  60 min/month
  ─────────────────────────────────────────────────────
  Total:                               = 257 min/month
  Remaining:                           = 1,743 min/month
  Usage:                               = 12.9% of free tier

BigQuery free tier: 10 GB storage, 1 TB queries/month

Our usage:
  Storage:   ~0.5 GB (star schema + marts for 1M records)  = 5%
  Queries:   ~5 GB/month (dashboard queries + mart rebuilds) = 0.5%
  Batch loads: unlimited (free)
```

### 14.4 Handling failures and catch-up

```
SCENARIO: Tuesday's 2 AM run fails (GitHub outage, BigQuery timeout)
──────────────────────────────────────────────────────────────────────

Tuesday 2:00 AM: daily_pipeline.yml triggers
Tuesday 2:05 AM: Pipeline fails (BigQuery API timeout)
Tuesday 2:06 AM: GitHub Actions marks run as FAILED (red ✗)
                 No data loaded for Tuesday

Wednesday 2:00 AM: daily_pipeline.yml triggers again
  Step 3 (simulate): Generates Wednesday's data files
  Step 4 (pipeline): Scans data/incoming/ for unprocessed files
    → Finds Tuesday's files (not in file registry — never processed)
    → Finds Wednesday's files (new)
    → Processes BOTH days' data in a single run
  Step 5 (marts): Rebuilds mart rows for both Tuesday + Wednesday

Result: Wednesday's dashboard shows complete data for both days.
        No manual intervention needed. No data loss.

This is idempotency — the pipeline's output depends on WHAT data
exists, not WHEN it was supposed to run.
```

---

## 15. What makes this portfolio-grade

1. **It runs while you sleep.** GitHub Actions triggers the pipeline at 2 AM daily. When a client clicks your dashboard link at 3 PM on a Tuesday, they see data from last night's run. Your laptop doesn't need to be on. That's a real pipeline, not a demo.

2. **It's containerized.** `docker compose up` — one command, full stack. No "install Python 3.11, then pip install these 30 packages, then set up BigQuery credentials." Clone, compose, done.

3. **The data feels real.** The simulator generates data with realistic seasonal patterns (Black Friday spikes, January returns), progressive quality degradation (schema changes, increasing nulls), and cross-channel entity overlap. It's not random noise — it's what business data actually looks like.

4. **Scale.** 1M+ historical records plus ongoing daily batches. Production-level volume, not a 100-row CSV demo.

5. **Real data movement.** Data physically moves between three databases (SQLite → DuckDB → BigQuery), crossing system boundaries the way real pipelines do.

6. **Cloud warehouse.** The analytical layer runs on BigQuery — a real cloud warehouse that Fortune 500 companies use. Not a local file pretending to be a warehouse.

7. **Incremental intelligence.** The pipeline knows what it's already processed. File registry with SHA-256 checksums, high-water marks, upsert logic. It processes only what's new.

8. **Self-healing and idempotent.** Missed run? The next run catches up automatically. Schema drift? Detected, logged, adapted. Bad data? Quarantined with reason codes, not silently dropped. The pipeline always completes.

9. **Multiple run modes.** Incremental, full refresh, source-specific, backfill, dry run. This is how production pipelines actually work.

10. **Data quality as a first-class concern.** Quality metrics tracked over time. Baselines maintained per source. Drift detected. Alerts fire on degradation. Quarantine review queue. This isn't "clean the data" — it's "operate a data quality program."

11. **The demo sells itself.** Client clicks a link, sees a live dashboard connected to BigQuery with yesterday's data. The README reads like a case study. The repo has Docker Compose, GitHub Actions CI, automated testing. The Loom video walks through the pipeline in 2 minutes. That's what wins contracts.

---

## 16. Future projects (same architecture, different domains)

**Project 2: HR/Payroll pipeline** — ADP/Gusto exports, attendance CSVs, performance reviews. Workforce analytics dashboards. Same architecture, different business logic.

**Project 3: Financial reconciliation** — Bank statements (OFX), QuickBooks exports, expense reports. Cash flow dashboards with automated bank-to-book reconciliation.

**Project 4: Healthcare clinic operations** — Appointment data, billing records, anonymized demographics. Operational dashboards (no-show rates, revenue per provider).

Each reuses 70% of the infrastructure (ingestion framework, profiling, orchestration, Docker, GitHub Actions, monitoring) with domain-specific business logic and dashboards. Three projects together tell the story: "Give me any messy data, from any industry, and I'll build the pipeline."

---

## 17. Project 1 vs future projects — what's reusable

```
                          Project 1    Project 2    Project 3
                          NovaMart     HR/Payroll   Finance
                          ─────────    ──────────   ─────────
Ingestion framework       BUILD        REUSE        REUSE
Profiling engine          BUILD        REUSE        REUSE
Validation framework      BUILD        REUSE        REUSE
Cleaning utilities        BUILD        REUSE (80%)  REUSE (80%)
Entity resolution         BUILD        REUSE (60%)  REUSE (40%)
Business transforms       BUILD        NEW          NEW
Star schema               BUILD        NEW          NEW
Dashboard framework       BUILD        REUSE (70%)  REUSE (70%)
Docker setup              BUILD        REUSE        REUSE
GitHub Actions            BUILD        REUSE        REUSE
Monitoring                BUILD        REUSE        REUSE
Simulator pattern         BUILD        NEW DATA     NEW DATA

Effort:                   100%         40%          40%
```
