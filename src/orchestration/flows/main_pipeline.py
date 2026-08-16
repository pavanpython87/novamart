"""Full pipeline DAG: ingests every configured source, profiles each raw
source, maps the order-bearing sources (shopify/amazon/pos) onto the
canonical order-line shape and the carrier feeds onto the canonical
shipments shape, validates/quarantines those canonical frames against
quality_rules.yaml, computes revenue economics, builds the analytics
marts, and writes everything to DuckDB.

Validation runs after canonical mapping rather than on each source's raw
data because quality_rules.yaml's rules are written against canonical
column names (order_id, gross_revenue, tracking_number, ...), which don't
exist until shopify/amazon/pos/fedex/ups/usps have been mapped onto their
shared shape — see _validate_canonical.

Per source, ingestion/profiling/validation failures are caught and logged
rather than raised, so one bad source doesn't block the others (see
PROJECT_PLAN.md 6.3's error-handling philosophy: the pipeline always
finishes with partial results rather than none). Prefect's built-in
retries (see the underlying @task definitions, e.g. ingest_source's
retries=3) handle transient failures before a source is given up on for
this run.

Sources are ingested sequentially rather than via Prefect's threaded task
runner: IncrementalTracker/QuarantineManager each hold a single sqlite3
connection that isn't safe to share across threads, and at this pipeline's
scale (8 sources, once a day) thread-level parallelism buys nothing worth
the added complexity — the same "don't add concurrency the workload
doesn't need" reasoning PROJECT_PLAN.md applies to skipping Kubernetes.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
from prefect import flow, get_run_logger

from src.cleaning.sku_mapper import SKUMapper
from src.ingestion.incremental_tracker import IncrementalTracker
from src.ingestion.registry import SourceConfig, load_sources
from src.load.bigquery_loader import BigQueryLoader
from src.load.dual_loader import DualLoader
from src.load.duckdb_loader import DuckDBLoader
from src.load.fact_builders import build_inventory_snapshot, build_shipments_fact
from src.orchestration.canonical_mapping import (
    CANONICAL_DEFAULTS,
    CANONICAL_FIELD_MAPS,
    DEDUP_KEYS,
    ORDER_SOURCES,
)
from src.orchestration.config import PipelineConfig, load_pipeline_config
from src.orchestration.tasks.dedup_tasks import dedup_orders
from src.orchestration.tasks.ingest_tasks import ingest_source
from src.orchestration.tasks.load_tasks import (
    load_table,
    write_bigquery_tables,
    write_duckdb_tables,
)
from src.orchestration.tasks.profile_tasks import profile_and_score
from src.orchestration.tasks.transform_tasks import (
    calculate_order_economics,
    map_to_canonical_orders,
)
from src.orchestration.tasks.validate_tasks import validate_and_quarantine
from src.profiling.baseline_manager import BaselineManager
from src.transform.mart_builder import build_all_marts
from src.validation.quarantine_manager import QuarantineManager

module_logger = logging.getLogger(__name__)

# Canonical order columns that must stay numeric across the Shopify/Amazon/POS
# concatenation: each source's raw values can arrive as strings (e.g. CSV
# dtype=str) or ints, and mixed-dtype groups break the mart aggregations once
# SKU mapping unifies cross-channel products under one product_key.
NUMERIC_ORDER_COLUMNS = [
    "quantity", "gross_revenue", "discount_amount", "refund_amount",
    "restocking_fee", "unit_cost", "platform_fee", "payment_processing_fee",
    "returns_and_refunds", "discounts_and_promotions", "net_revenue",
    "cogs", "gross_profit",
]


def _run_logger():
    try:
        return get_run_logger()
    except Exception:
        return module_logger


def _ingest_all_sources(sources: dict[str, SourceConfig], tracker: IncrementalTracker) -> dict[str, pd.DataFrame]:
    """Ingests every configured source. Each source is independent: one
    failing after its retries are exhausted contributes an empty DataFrame
    rather than aborting the run for the others."""
    run_logger = _run_logger()
    raw_frames: dict[str, pd.DataFrame] = {}
    for name, source in sources.items():
        try:
            raw_frames[name] = ingest_source(source, tracker)
        except Exception as exc:
            run_logger.warning("Ingestion failed for source=%s after retries: %s", name, exc)
            raw_frames[name] = pd.DataFrame()
    return raw_frames


def _profile_sources(
    raw_frames: dict[str, pd.DataFrame], baseline_manager: BaselineManager,
) -> dict[str, dict]:
    """Profiles each non-empty source and returns its quality scorecard.

    Business-rule validation/quarantine no longer happens per-raw-source
    here: quality_rules.yaml is defined in terms of canonical column names
    (order_id, gross_revenue, tracking_number, ship_date_key, ...), which
    only exist after canonical field mapping — a raw Shopify/FedEx frame's
    native columns (Name/Total, TrackingNumber/ShipDate) never matched
    those rule names, so every rule silently skipped. See
    _validate_canonical, called on the canonical orders/shipments frames
    later in this flow, for where validation actually runs now."""
    run_logger = _run_logger()
    scorecards: dict[str, dict] = {}

    for name, raw_df in raw_frames.items():
        if raw_df.empty:
            continue
        try:
            profile_result = profile_and_score(raw_df, name, baseline_manager)
            scorecards[name] = profile_result["scorecard"]
        except Exception as exc:
            run_logger.warning("Profiling failed for source=%s: %s", name, exc)

    return scorecards


def _validate_canonical(
    df: pd.DataFrame, rules_key: str, quarantine_manager: QuarantineManager, batch_id: str,
) -> pd.DataFrame:
    """Runs quality_rules.yaml's business rules for `rules_key` ("orders" or
    "shipments") against a canonical (post-mapping) DataFrame, quarantining
    failing rows. A validation error logs a warning and passes the data
    through unchanged rather than failing the whole run."""
    if df.empty:
        return df
    run_logger = _run_logger()
    try:
        result = validate_and_quarantine(df, rules_key, quarantine_manager, batch_id=batch_id)
        return result["clean_df"]
    except Exception as exc:
        run_logger.warning("Validation failed for %s, passing data through: %s", rules_key, exc)
        return df


def _map_channel_products(canonical: pd.DataFrame, channel: str,
                          sku_mapper: SKUMapper) -> pd.DataFrame:
    """Resolves a channel's raw SKU/ASIN/internal-SKU product_key to the
    unified catalog product_id via SKUMapper. Unresolved keys fall back to
    their original value so no line is lost."""
    if canonical.empty or "product_key" not in canonical.columns:
        return canonical

    map_fn = {
        "shopify": sku_mapper.map_shopify,
        "amazon": sku_mapper.map_amazon,
        "pos": sku_mapper.map_pos,
    }[channel]

    mapped = canonical.copy()
    mapped["product_key"] = canonical["product_key"].map(
        lambda v: map_fn(str(v)) if pd.notna(v) else None,
    )
    unresolved = mapped["product_key"].isna() & canonical["product_key"].notna()
    mapped.loc[unresolved, "product_key"] = canonical.loc[unresolved, "product_key"]
    return mapped


def _build_sku_mapper(products_df: pd.DataFrame) -> SKUMapper | None:
    """Builds a SKUMapper from the ingested product catalog. Near-duplicate
    catalog rows (product_id suffixed "-DUP", injected by the simulator)
    are dropped so they don't overwrite the canonical SKU mapping."""
    if products_df is None or products_df.empty or "product_id" not in products_df.columns:
        return None
    catalog = products_df.copy()
    catalog = catalog[~catalog["product_id"].astype(str).str.endswith("-DUP")]
    catalog = catalog.drop_duplicates(subset=["product_id"])
    return SKUMapper(catalog)


def build_orders(source_frames: dict[str, pd.DataFrame],
                 sku_mapper: SKUMapper | None = None) -> pd.DataFrame:
    """Maps each order-bearing source's clean DataFrame onto the canonical
    order-line shape, resolves channel SKUs to the unified product_id when
    a SKUMapper is available, deduplicates within each source, concatenates
    them, and computes revenue/profit economics."""
    canonical_frames = []
    for channel in ORDER_SOURCES:
        df = source_frames.get(channel)
        if df is None or df.empty:
            continue
        dedup_keys = DEDUP_KEYS[channel]
        deduped = dedup_orders(df, key_columns=dedup_keys)["deduped_df"]
        canonical = map_to_canonical_orders(
            deduped, channel, CANONICAL_FIELD_MAPS[channel], defaults=CANONICAL_DEFAULTS[channel],
        )
        if sku_mapper is not None:
            canonical = _map_channel_products(canonical, channel, sku_mapper)
        canonical_frames.append(canonical)

    if not canonical_frames:
        return pd.DataFrame()
    orders = pd.concat(canonical_frames, ignore_index=True)
    orders = calculate_order_economics(orders)
    for col in NUMERIC_ORDER_COLUMNS:
        if col in orders.columns:
            orders[col] = pd.to_numeric(orders[col], errors="coerce")
    return orders


def _merge_stg_orders(duckdb_loader: DuckDBLoader, orders: pd.DataFrame) -> pd.DataFrame:
    """Appends this run's orders to the existing stg_orders table, making
    the staging table cumulative across incremental runs.

    Idempotency comes from dropping exact-duplicate lines: re-processing
    the same files (which the file registry already prevents) or a
    catch-up run can never duplicate a line already stored. When there are
    no new orders, the existing table is returned unchanged."""
    try:
        existing = duckdb_loader.conn.execute("SELECT * FROM stg_orders").fetchdf()
    except Exception:
        existing = pd.DataFrame()

    if orders.empty:
        return existing

    combined = pd.concat([existing, orders], ignore_index=True)
    # A DuckDB round-trip can change column dtypes (e.g. an object-dtype
    # `quantity` becomes VARCHAR), which would otherwise break the numeric
    # aggregations in mart_builder when mixed with fresh in-memory data.
    for col in NUMERIC_ORDER_COLUMNS:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")
    return combined.drop_duplicates(ignore_index=True)


def _build_bigquery_loader(config: PipelineConfig) -> BigQueryLoader | None:
    """Constructs a BigQueryLoader when the configured backend needs one,
    falling back to None (duckdb-only) on a missing project id or client
    construction failure — mirrors dashboard/db_connector.py's
    _resolve_backend fallback, so a misconfigured/unavailable BigQuery
    backend degrades the run rather than failing it outright."""
    if config.warehouse_backend not in ("bigquery", "both"):
        return None
    if not config.bq_project_id:
        module_logger.warning(
            "WAREHOUSE_BACKEND=%s but BQ_PROJECT_ID is not set; writing to DuckDB only.",
            config.warehouse_backend,
        )
        return None
    try:
        loader = BigQueryLoader(project_id=config.bq_project_id, dataset=config.bq_dataset)
        loader.ensure_dataset()
        loader.ensure_table("fact_shipments")
        loader.ensure_table("fact_inventory_daily")
        return loader
    except Exception as exc:
        module_logger.warning("BigQuery unavailable (%s); writing to DuckDB only.", exc)
        return None


@flow(name="main-pipeline")
def main_pipeline(
    tracker_db: str = "data/landing/novamart_tracker.db",
    baseline_dir: str = "data/landing/baselines",
    quarantine_db: str = "data/quarantine/novamart_quarantine.db",
    serving_db: str = "data/serving/novamart_serving.duckdb",
    sources_config: str = "config/pipeline_config.yaml",
    batch_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Runs the full pipeline once: ingest every configured source, profile
    each, build the canonical order/shipment sets and validate/quarantine
    them, compute marts, and write everything to the serving warehouse.

    Returns a summary dict: per-source row counts, quality scorecards, mart
    row counts, and the list of tables actually written. When dry_run is
    True the pipeline ingests/profiles/validates but skips the warehouse
    write (see PROJECT_PLAN.md 3.2's DRY RUN mode).
    """
    batch_id = batch_id or dt.datetime.now(dt.UTC).isoformat()
    sources = load_sources(sources_config)
    tracker = IncrementalTracker(tracker_db)
    baseline_manager = BaselineManager(baseline_dir)
    quarantine_manager = QuarantineManager(quarantine_db)

    raw_frames = _ingest_all_sources(sources, tracker)
    tracker.close()
    scorecards = _profile_sources(raw_frames, baseline_manager)

    products_df = raw_frames.get("products", pd.DataFrame())
    sku_mapper = _build_sku_mapper(products_df)
    orders = build_orders(raw_frames, sku_mapper=sku_mapper)
    orders = _validate_canonical(orders, "orders", quarantine_manager, batch_id)

    run_date = dt.datetime.now(dt.UTC).date()
    shipments_fact = build_shipments_fact(raw_frames)
    shipments_fact = _validate_canonical(shipments_fact, "shipments", quarantine_manager, batch_id)
    inventory_fact = build_inventory_snapshot(products_df, snapshot_date=run_date)
    inventory_snapshot = inventory_fact.rename(columns={"snapshot_date_key": "snapshot_date"})
    preview_marts = (
        build_all_marts(orders, inventory_snapshot=inventory_snapshot)
        if not orders.empty else {}
    )

    if dry_run:
        return {
            "batch_id": batch_id,
            "dry_run": True,
            "source_row_counts": {name: len(df) for name, df in raw_frames.items()},
            "quality": scorecards,
            "order_row_count": len(orders),
            "shipment_row_count": len(shipments_fact),
            "inventory_row_count": len(inventory_fact),
            "mart_row_counts": {name: len(df) for name, df in preview_marts.items()},
            "tables_written": [],
        }

    config = load_pipeline_config(sources_config)
    bigquery_loader = _build_bigquery_loader(config)
    effective_backend = config.warehouse_backend if bigquery_loader is not None else "duckdb"

    duckdb_loader = DuckDBLoader(serving_db)
    duckdb_loader.create_schema()
    dual_loader = DualLoader(duckdb_loader, bigquery_loader=bigquery_loader, backend=effective_backend)

    all_orders = _merge_stg_orders(duckdb_loader, orders)
    marts = (
        build_all_marts(all_orders, inventory_snapshot=inventory_snapshot)
        if not all_orders.empty else {}
    )
    tables_to_write = {"stg_orders": all_orders, **marts}
    written = write_duckdb_tables(duckdb_loader, tables_to_write)
    bq_written = write_bigquery_tables(bigquery_loader, tables_to_write) if bigquery_loader else []

    # Load the non-order facts (shipping + inventory) into their star-schema
    # tables via DualLoader (keyed upserts, to both DuckDB and, when
    # configured, BigQuery) rather than the create-or-replace staging path
    # above, so incremental runs accumulate.
    facts_written = []
    if not shipments_fact.empty:
        load_table("fact_shipments", shipments_fact, dual_loader)
        facts_written.append("fact_shipments")
    if not inventory_fact.empty:
        load_table("fact_inventory_daily", inventory_fact, dual_loader)
        facts_written.append("fact_inventory_daily")

    duckdb_loader.close()

    return {
        "batch_id": batch_id,
        "source_row_counts": {name: len(df) for name, df in raw_frames.items()},
        "quality": scorecards,
        "order_row_count": len(orders),
        "stg_orders_row_count": len(all_orders),
        "shipment_row_count": len(shipments_fact),
        "inventory_row_count": len(inventory_fact),
        "mart_row_counts": {name: len(df) for name, df in marts.items()},
        "tables_written": written + facts_written,
        "warehouse_backend": effective_backend,
        "bigquery_tables_written": (bq_written + facts_written) if bigquery_loader else [],
    }
