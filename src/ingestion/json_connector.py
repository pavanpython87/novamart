"""JSON connector: nested transaction flattening (POS v3/v4 schema variants)
and malformed/truncated JSON recovery.

POS exports wrap a list of transactions in a batch envelope. Each transaction
nests its line items differently depending on schema version:
  v3: transaction["items"] is a flat array at the transaction root.
  v4: transaction["line_items"]["items"] nests the items one level deeper.
This connector normalizes both into a single "items" list before flattening,
so downstream consumers never need to know which POS version produced a row.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from src.ingestion.base_connector import BaseConnector


def _normalize_transaction(txn: dict) -> dict:
    """Flattens v3/v4 structural differences into one consistent shape."""
    txn = dict(txn)
    if "line_items" in txn:
        items = txn.pop("line_items", {}).get("items", [])
    else:
        items = txn.pop("items", [])
    txn["items"] = items
    txn["item_count"] = len(items)

    payment = txn.get("payment") or {}
    if "instrument" in payment:
        txn["payment"] = {**payment, "card_type": payment["instrument"].get("type")}
    return txn


def _recover_truncated_json(text: str) -> dict | None:
    """Best-effort recovery for a JSON payload truncated mid-write (e.g. a
    process killed while streaming output). Finds the last complete
    transaction object inside a truncated "transactions" array and closes
    the structure, discarding the incomplete tail record."""
    match = re.search(r'"transactions"\s*:\s*\[', text)
    if not match:
        return None
    array_start = match.end()
    depth = 0
    last_complete_end = None
    in_string = False
    escape = False
    for i in range(array_start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_complete_end = i + 1
    if last_complete_end is None:
        return None
    recovered = text[:array_start] + text[array_start:last_complete_end] + "]}"
    try:
        return json.loads(recovered)
    except json.JSONDecodeError:
        return None


class JSONConnector(BaseConnector):
    def __init__(self, source_path, records_key: str = "transactions"):
        super().__init__(source_path)
        self.records_key = records_key
        self.recovered = False

    def connect(self) -> None:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)
        self._connected = True

    def extract(self) -> pd.DataFrame:
        text = self.source_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = _recover_truncated_json(text)
            if payload is None:
                raise
            self.recovered = True

        records = payload.get(self.records_key, []) if isinstance(payload, dict) else payload
        normalized = [_normalize_transaction(r) for r in records]
        if not normalized:
            return pd.DataFrame()
        return pd.json_normalize(normalized, sep=".")
