"""Maps source definitions in config/pipeline_config.yaml to their
connector classes, so the orchestrator can go from a source name straight
to a ready-to-run connector without hardcoding per-source wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.ingestion.base_connector import BaseConnector
from src.ingestion.csv_connector import CSVConnector
from src.ingestion.excel_connector import ExcelConnector
from src.ingestion.flat_file_connector import FlatFileConnector
from src.ingestion.json_connector import JSONConnector
from src.ingestion.sqlite_connector import SQLiteConnector
from src.ingestion.xml_connector import XMLConnector

DEFAULT_CONFIG_PATH = Path("config/pipeline_config.yaml")

CONNECTOR_MAP: dict[str, type[BaseConnector]] = {
    "csv": CSVConnector,
    "xlsx": ExcelConnector,
    "json": JSONConnector,
    "xml": XMLConnector,
    "sqlite": SQLiteConnector,
    "flat_file": FlatFileConnector,
}

# Format-specific extras that aren't expressible in the generic YAML source
# schema (e.g. the USPS flat-file column layout, since USPS/UPS both share
# a "shipping" incoming_dir but need different parsing).
SOURCE_EXTRA_KWARGS: dict[str, dict] = {
    "shipping_usps": {
        "columns": ["tracking_number", "reference_order_id", "ship_date",
                     "delivery_date", "status", "weight_oz"],
        "delimiter": "|",
    },
    "products": {"table": "products"},
}


@dataclass
class SourceConfig:
    name: str
    format: str
    incoming_dir: Path
    incremental_mode: str
    file_pattern: str | None = None
    hwm_column: str | None = None


def load_sources(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, SourceConfig]:
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    sources = {}
    for name, cfg in raw.get("sources", {}).items():
        sources[name] = SourceConfig(
            name=name,
            format=cfg["format"],
            incoming_dir=Path(cfg["incoming_dir"]),
            incremental_mode=cfg["incremental_mode"],
            file_pattern=cfg.get("file_pattern"),
            hwm_column=cfg.get("hwm_column"),
        )
    return sources


def build_connector(source: SourceConfig, file_path: str | Path) -> BaseConnector:
    """Instantiates the correct connector class for a source's format,
    applying any format-specific extra kwargs registered above."""
    connector_cls = CONNECTOR_MAP.get(source.format)
    if connector_cls is None:
        raise ValueError(f"No connector registered for format '{source.format}'")
    extra_kwargs = SOURCE_EXTRA_KWARGS.get(source.name, {})
    return connector_cls(file_path, **extra_kwargs)
