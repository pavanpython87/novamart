# Data Dictionary

Tables actually written by the pipeline (see `docs/architecture.md` for
why the full dimensional schema in `schema_manager.py` isn't fully
populated). All tables live in the serving warehouse
(`data/serving/novamart_serving.duckdb` locally, or the configured
BigQuery dataset when `WAREHOUSE_BACKEND=bigquery|both`).

## stg_orders

Canonical, cumulative order-line table. One row per (order, product) line
item, across all three order-bearing channels (shopify/amazon/pos).
Written by `main_pipeline.build_orders()` and merged in via
`_merge_stg_orders` (exact-duplicate-row drop, so re-running never
double-counts). Every mart is derived from this table.

| Column | Type | Notes |
|---|---|---|
| `order_id` | string | Raw channel order id (Shopify `Name`, Amazon `amazon-order-id`, POS `transaction_id`) |
| `customer_key` | string | Raw channel customer identifier (not yet resolved to a unified customer — see `src/dedup/customer_resolver.py` for the fuzzy-match logic, not currently wired into `main_pipeline`) |
| `customer_email` | string | Shopify only; null for amazon/pos |
| `order_date` | date/string | Order timestamp, channel-native format normalized during ingestion |
| `gross_revenue` | float | Line total before fees/discounts/returns |
| `quantity` | float | Units on this line |
| `discount_amount` | float | |
| `product_key` | string | Resolved to the unified catalog `product_id` via `SKUMapper` when the `products` source is configured; falls back to the raw SKU/ASIN otherwise |
| `status` | string | Shopify/Amazon only (`Financial Status` / `order-status`) |
| `payment_method` | string | POS native; defaults to `"card"` for shopify/amazon |
| `channel` | string | `shopify` \| `amazon` \| `pos` |
| `refund_amount`, `restocking_fee`, `unit_cost` | float | Default `0.0` unless the source provides them |
| `platform_fee`, `payment_processing_fee` | float | Computed by `revenue_calculator.py` from `gross_revenue`/`payment_method`/channel |
| `returns_and_refunds`, `discounts_and_promotions` | float | Computed from `refund_amount`/`restocking_fee`/`discount_amount` |
| `net_revenue` | float | `gross_revenue - fees - returns - discounts` |
| `cogs` | float | `unit_cost * quantity` |
| `gross_profit` | float | `net_revenue - cogs` |

Rows failing `quality_rules.yaml`'s `orders` rules (`gross_revenue >= 0`,
`order_date <= today`) are quarantined before reaching this table (see
`data_quality` section below).

## fact_shipments

One row per tracking number, unioned across all three carriers via
`src/load/fact_builders.py::build_shipments_fact`. Upserted (keyed
delete-then-insert on `tracking_number`), so re-processing the same
tracking number updates it in place.

| Column | Type | Notes |
|---|---|---|
| `tracking_number` | string | Primary key |
| `order_id` | string | |
| `carrier` | string | `fedex` \| `ups` \| `usps` |
| `ship_date_key` | date | |
| `delivery_date_key` | date | Null if not yet delivered |
| `shipping_cost` | float | Estimated: `base_cost + weight_kg * per_kg_rate`, carrier-specific constants in `fact_builders.py` |

`shipments` rules in `quality_rules.yaml` (`delivery_date_key >=
ship_date_key`) are `on_fail: warn`, not `quarantine` — a shipment that
hasn't been delivered yet, or was delivered "before" it shipped due to a
data-entry error, still ships through; it's flagged, not dropped.

## fact_inventory_daily

One row per catalog product per snapshot date. Upserted on `product_key`
(one row per product per pipeline run — not a real daily history table
yet; each run overwrites the previous snapshot for that product).

| Column | Type | Notes |
|---|---|---|
| `product_key` | string | = `product_id` from the catalog |
| `snapshot_date_key` | date | |
| `on_hand_qty` | int | Deterministic pseudo-stock seeded from `product_id` (the catalog source has no real stock column) |
| `lead_time_days` | int | Same deterministic-seed approach |

## Mart tables (`src/transform/mart_builder.py`)

All five are fully rebuilt (not incrementally updated) from `stg_orders`
(+ `fact_inventory_daily` for `mart_inventory_health`) every pipeline run,
and by `rebuild_marts_flow` on its own schedule.

**mart_revenue_daily** — `build_time_series(orders, "daily")`

| Column | Type |
|---|---|
| `period` | date (day bucket) |
| `net_revenue` | float |
| `order_count` | int |

**mart_customer_ltv** — `build_customer_analytics`

| Column | Type | Notes |
|---|---|---|
| `customer_key` | string | |
| `aov` | float | Average order value |
| `clv` | float | Sum of net_revenue per customer |
| `purchase_frequency` | float | Orders / customer lifetime |
| `days_since_last_order` | int | |
| `churn_risk` | string | `low` \| `medium` \| `high`, thresholded on `days_since_last_order` |
| `recency`, `frequency`, `monetary` | float | RFM raw inputs |
| `r_score`, `f_score`, `m_score` | int (1-5) | Quintile scores |
| `rfm_segment` | string | Concatenated `"{r}{f}{m}"`, e.g. `"555"` |

**mart_product_performance** — grouped by `product_key`

| Column | Type |
|---|---|
| `product_key` | string |
| `units_sold` | float |
| `gross_revenue`, `net_revenue`, `gross_profit` | float |

**mart_inventory_health** — merges sell-through + reorder-point + dead-stock flag

| Column | Type | Notes |
|---|---|---|
| `product_key` | string | |
| `units_sold`, `beginning_inventory` | float | |
| `sell_through_rate` | float | `units_sold / beginning_inventory` |
| `avg_daily_sales` | float | |
| `lead_time_days` | int | From `fact_inventory_daily` |
| `reorder_point` | float | `avg_daily_sales * lead_time_days` (+ safety stock) |
| `is_dead_stock` | bool | No sales within the dead-stock lookback window |

**mart_channel_performance** — grouped by `channel`

| Column | Type |
|---|---|
| `channel` | string |
| `order_count` | int |
| `gross_revenue`, `platform_fee`, `payment_processing_fee`, `net_revenue`, `gross_profit` | float |

## Quarantine tables

`data/quarantine/novamart_quarantine.db` (SQLite), one table per
canonical rules-key that has ever quarantined a row: `quarantine_orders`,
`quarantine_shipments` (only created if a `warn`-only rule routes to
quarantine — currently shipments never populates this table since its
only rule is `on_fail: warn`). Schema = the source DataFrame's columns
plus:

| Column | Type | Notes |
|---|---|---|
| `reason_codes` | string | Comma-joined rule names that failed, e.g. `"gross_revenue_positive"` |
| `batch_id` | string | Which pipeline run quarantined this row |
| `quarantined_at` | ISO timestamp | |

## Unused star-schema tables

`dim_customers`, `dim_products`, `dim_dates`, `dim_channels`,
`fact_orders`, `fact_returns` are defined in `schema_manager.py` (DDL is
created by `DuckDBLoader.create_schema()`) but nothing in `main_pipeline`
currently writes to them — `stg_orders` (a flat, denormalized table) and
the five marts serve that purpose today. See `docs/architecture.md`.
