"""CSV connector: encoding detection, dialect sniffing, and BOM handling.

No external encoding-detection dependency (e.g. chardet) is used — a small
priority-ordered decode attempt is sufficient for the encodings this
pipeline actually encounters (UTF-8 with/without BOM, Windows-1252).
"""

from __future__ import annotations

import csv
import io

import pandas as pd

from src.ingestion.base_connector import BaseConnector

CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]


def detect_encoding(raw_bytes: bytes) -> str:
    for encoding in CANDIDATE_ENCODINGS:
        try:
            raw_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"  # last resort: latin-1 never raises


def detect_dialect(sample_text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
    except csv.Error:
        return csv.excel  # default comma dialect


class CSVConnector(BaseConnector):
    def __init__(self, source_path, encoding: str | None = None, sep: str | None = None):
        super().__init__(source_path)
        self._forced_encoding = encoding
        self._forced_sep = sep
        self.encoding: str | None = None
        self.sep: str | None = None

    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        self._connected = True

    def extract(self) -> pd.DataFrame:
        raw_bytes = self.source_path.read_bytes()
        self.encoding = self._forced_encoding or detect_encoding(raw_bytes)
        text = raw_bytes.decode(self.encoding)

        sample = "\n".join(text.splitlines()[:20])
        dialect = detect_dialect(sample)
        self.sep = self._forced_sep or dialect.delimiter

        # Skip fully-blank lines (Shopify export quirk: blank rows between blocks)
        cleaned = "\n".join(line for line in text.splitlines() if line.strip() != "")
        df = pd.read_csv(io.StringIO(cleaned), sep=self.sep, dtype=str, keep_default_na=False,
                          na_values=[""])
        return df
