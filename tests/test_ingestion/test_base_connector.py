import pandas as pd
import pytest

from src.ingestion.base_connector import (
    BaseConnector,
    compute_file_hash,
    schema_fingerprint,
)


class _DummyConnector(BaseConnector):
    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)

    def extract(self) -> pd.DataFrame:
        return pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def test_base_connector_is_abstract():
    with pytest.raises(TypeError):
        BaseConnector("somefile.csv")  # type: ignore[abstract]


def test_run_produces_metadata_envelope(tmp_path):
    f = tmp_path / "dummy.csv"
    f.write_text("a,b\n1,x\n2,y\n")
    result = _DummyConnector(f).run()
    assert result.metadata["row_count"] == 2
    assert result.metadata["source_file"] == str(f)
    assert "schema_fingerprint" in result.metadata
    assert len(result.metadata["file_hash"]) == 64  # sha256 hex digest


def test_compute_file_hash_is_deterministic(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world")
    assert compute_file_hash(f) == compute_file_hash(f)


def test_schema_fingerprint_reflects_dtypes():
    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    fp = schema_fingerprint(df)
    assert "x:int64" in fp
    assert f"y:{df['y'].dtype}" in fp
