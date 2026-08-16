"""Per-source ingestion tasks: scan a source's incoming directory for
new/changed files, extract them via the registered connector, and record
processed state in the IncrementalTracker so re-running the pipeline is
idempotent (already-seen, unchanged files are skipped).
"""

from __future__ import annotations

import logging
import zipfile

import pandas as pd
from lxml import etree
from prefect import task
from prefect.cache_policies import NO_CACHE

from src.ingestion import file_watcher
from src.ingestion.incremental_tracker import IncrementalTracker
from src.ingestion.registry import SourceConfig, build_connector

logger = logging.getLogger(__name__)

# Malformed-file errors the chaos injector is expected to produce (emptied/
# truncated CSV & JSON, corrupted XLSX, broken XML). These are data
# problems with one file, not transient/infra failures, so they should be
# logged and skipped rather than aborting the whole source's batch.
EXTRACT_ERRORS = (
    pd.errors.EmptyDataError,
    pd.errors.ParserError,
    ValueError,       # covers json.JSONDecodeError
    OSError,
    zipfile.BadZipFile,   # corrupted .xlsx (Amazon settlement files)
    etree.LxmlError,      # covers etree.XMLSyntaxError (FedEx feeds)
)


def _extract_as_dataframe(connector) -> pd.DataFrame:
    result = connector.extract()
    if isinstance(result, pd.DataFrame):
        return result
    return pd.concat(result.values(), ignore_index=True)


def _ingest_file_registry_source(source: SourceConfig, tracker: IncrementalTracker) -> pd.DataFrame:
    files = file_watcher.scan_incoming(source.incoming_dir, source.file_pattern)
    frames = []
    for file_path in files:
        if not tracker.is_new_or_changed(source.name, file_path):
            continue
        connector = build_connector(source, file_path)
        try:
            df = _extract_as_dataframe(connector)
        except EXTRACT_ERRORS as exc:
            # One corrupted file (chaos injection: emptied/truncated/malformed)
            # shouldn't take down every other valid file for this source.
            # Mark it processed with row_count=0 so it isn't retried forever
            # — it will keep failing the same way until the file changes.
            logger.warning("Skipping unparseable file source=%s file=%s error=%s",
                            source.name, file_path, exc)
            tracker.mark_processed(source.name, file_path, row_count=0)
            continue
        frames.append(df)
        tracker.mark_processed(source.name, file_path, row_count=len(df))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _ingest_hwm_source(source: SourceConfig, tracker: IncrementalTracker) -> pd.DataFrame:
    files = file_watcher.scan_incoming(source.incoming_dir, source.file_pattern)
    if not files:
        return pd.DataFrame()
    connector = build_connector(source, files[0])
    if hasattr(connector, "hwm_value"):
        connector.hwm_column = source.hwm_column
        connector.hwm_value = tracker.get_hwm(source.name, source.hwm_column)
    df = connector.extract()
    max_hwm = getattr(connector, "max_hwm_value", None)
    if max_hwm is not None:
        tracker.set_hwm(source.name, source.hwm_column, max_hwm)
    return df


@task(name="ingest-source", retries=3, retry_delay_seconds=10, cache_policy=NO_CACHE)
def ingest_source(source: SourceConfig, tracker: IncrementalTracker) -> pd.DataFrame:
    """Ingests all new/changed data for one source. Each source ingests
    independently, so a failure here (after retries) doesn't have to block
    other sources — the calling flow decides how to handle that.

    Caching is disabled: `tracker` wraps a live sqlite3.Connection, which
    can't be hashed/pickled into a cache key (Prefect would otherwise log
    a hashing error on every call and silently skip persisting a result)."""
    if source.incremental_mode == "high_water_mark":
        return _ingest_hwm_source(source, tracker)
    return _ingest_file_registry_source(source, tracker)
