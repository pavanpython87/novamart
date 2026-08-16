"""Pipeline configuration for orchestration: merges config/pipeline_config.yaml
with environment variable overrides (the latter used by GitHub Actions /
Docker to inject secrets and per-environment settings without editing YAML).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = "config/pipeline_config.yaml"


@dataclass
class PipelineConfig:
    warehouse_backend: str
    landing_db: str
    quarantine_db: str
    processing_db: str
    serving_db: str
    bq_project_id: str | None = None
    bq_dataset: str = "novamart"
    sources: dict = field(default_factory=dict)
    quality_gate_thresholds: dict = field(default_factory=dict)


def load_pipeline_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> PipelineConfig:
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    warehouse = raw.get("warehouse", {})

    return PipelineConfig(
        warehouse_backend=os.environ.get("WAREHOUSE_BACKEND", warehouse.get("backend", "duckdb")),
        landing_db=warehouse.get("landing_db", "data/landing/novamart_landing.db"),
        quarantine_db=warehouse.get("quarantine_db", "data/quarantine/novamart_quarantine.db"),
        processing_db=warehouse.get("processing_db", "data/processing/novamart_processing.duckdb"),
        serving_db=warehouse.get("serving_db", "data/serving/novamart_serving.duckdb"),
        bq_project_id=os.environ.get("BQ_PROJECT_ID"),
        bq_dataset=os.environ.get("BQ_DATASET", "novamart"),
        sources=raw.get("sources", {}),
        quality_gate_thresholds=raw.get("quality_gate_thresholds", {}),
    )
