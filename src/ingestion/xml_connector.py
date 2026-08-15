"""XML connector: namespace-aware XPath extraction for the FedEx shipping
feed (and any other namespaced per-record XML export).
"""

from __future__ import annotations

import re

import pandas as pd
from lxml import etree

from src.ingestion.base_connector import BaseConnector


def _detect_namespace(root: etree._Element) -> str | None:
    match = re.match(r"\{(.+?)\}", root.tag)
    return match.group(1) if match else None


class XMLConnector(BaseConnector):
    def __init__(self, source_path, record_tag: str = "Shipment"):
        super().__init__(source_path)
        self.record_tag = record_tag
        self.namespace: str | None = None

    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        self._connected = True

    def extract(self) -> pd.DataFrame:
        tree = etree.parse(str(self.source_path))
        root = tree.getroot()
        self.namespace = _detect_namespace(root)

        tag = f"{{{self.namespace}}}{self.record_tag}" if self.namespace else self.record_tag
        records = []
        for el in root.iter(tag):
            row = {}
            for child in el:
                local_name = etree.QName(child.tag).localname
                row[local_name] = child.text
            records.append(row)
        return pd.DataFrame(records)
