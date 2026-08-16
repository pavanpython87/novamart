

from src.orchestration.config import load_pipeline_config


def test_load_pipeline_config_reads_yaml_defaults():
    config = load_pipeline_config("config/pipeline_config.yaml")
    assert config.warehouse_backend == "duckdb"
    assert "shopify" in config.sources
    assert config.quality_gate_thresholds["row_count_drop_fail_pct"] == 50


def test_env_var_overrides_warehouse_backend(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_BACKEND", "both")
    config = load_pipeline_config("config/pipeline_config.yaml")
    assert config.warehouse_backend == "both"


def test_bq_project_id_from_env(monkeypatch):
    monkeypatch.setenv("BQ_PROJECT_ID", "my-project")
    config = load_pipeline_config("config/pipeline_config.yaml")
    assert config.bq_project_id == "my-project"


def test_bq_project_id_defaults_to_none(monkeypatch):
    monkeypatch.delenv("BQ_PROJECT_ID", raising=False)
    config = load_pipeline_config("config/pipeline_config.yaml")
    assert config.bq_project_id is None
