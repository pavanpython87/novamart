"""Mechanics for injecting the five categorized issue types described in
the project plan (section 13.2): format, data quality, schema drift,
semantic conflicts, and encoding problems.

Row-level functions operate on `list[dict]` and return a new list (never
mutate in place, so callers can compare before/after for tests and
reports). File-level functions operate on already-written files to
simulate duplicate uploads, truncation, and encoding corruption.

`quality_degrader.py` decides *how much* of each issue to apply for a
given date; this module only knows *how* to apply it. A `level` multiplier
(default 1.0) scales every rate uniformly for ad-hoc "extreme testing"
(see project plan section 13.4, `--chaos-level`).
"""

from __future__ import annotations

import copy
import random
import shutil
import unicodedata
from pathlib import Path

TEST_DATA_NAMES = [("John", "Doe"), ("Test", "User"), ("Jane", "Tester")]
TEST_DATA_EMAILS = ["test@test.com", "test@example.com", "asdf@asdf.com"]
TEST_DATA_ADDRESS = "123 Main St"

HTML_ENTITY_MAP = {"&": "&amp;", "'": "&#39;", '"': "&quot;"}
INVISIBLE_CHARS = ["\u200b", "\u00a0"]  # zero-width space, non-breaking space

CURRENCY_PREFIXES = ["$", "USD ", "CAD "]


def _rate(base_rate: float, level: float) -> float:
    return min(base_rate * level, 1.0)


# -- CATEGORY: data quality ----------------------------------------------

def inject_duplicate_rows(rows: list[dict], rate: float = 0.02, level: float = 1.0,
                           rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    result = list(rows)
    for row in rows:
        if rng.random() < rate:
            result.append(copy.deepcopy(row))
    rng.shuffle(result)
    return result


def inject_trailing_whitespace(rows: list[dict], fields: list[str], rate: float = 0.10,
                                level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            if field in row and isinstance(row[field], str) and rng.random() < rate:
                row[field] = row[field] + rng.choice([" ", "  ", "\t"])
        out.append(row)
    return out


def inject_mixed_case(rows: list[dict], field: str, rate: float = 0.30, level: float = 1.0,
                       rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    transforms = [str.upper, str.lower, str.title]
    out = []
    for row in rows:
        row = dict(row)
        if field in row and isinstance(row[field], str) and rng.random() < rate:
            row[field] = rng.choice(transforms)(row[field])
        out.append(row)
    return out


def inject_null_required_fields(rows: list[dict], fields: list[str], rate: float = 0.03,
                                 level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            if field in row and rng.random() < rate:
                row[field] = None
        out.append(row)
    return out


def inject_negative_amounts(rows: list[dict], fields: list[str], rate: float = 0.005,
                             level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            if field in row and isinstance(row[field], (int, float)) and rng.random() < rate:
                row[field] = -abs(row[field])
        out.append(row)
    return out


def inject_future_dates(rows: list[dict], field: str, days_ahead: tuple[int, int] = (1, 60),
                         rate: float = 0.003, level: float = 1.0,
                         rng: random.Random | None = None) -> list[dict]:
    import datetime as dt
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        if field in row and rng.random() < rate:
            row[field] = (dt.date.today() + dt.timedelta(days=rng.randint(*days_ahead))).isoformat()
        out.append(row)
    return out


def inject_test_data(rows: list[dict], name_fields: tuple[str, str] | None,
                      email_field: str | None, rate: float = 0.01, level: float = 1.0,
                      rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        if rng.random() < rate:
            if name_fields:
                first, last = rng.choice(TEST_DATA_NAMES)
                row[name_fields[0]] = first
                row[name_fields[1]] = last
            if email_field and email_field in row:
                row[email_field] = rng.choice(TEST_DATA_EMAILS)
        out.append(row)
    return out


# -- CATEGORY: format issues ----------------------------------------------

def inject_currency_symbols(rows: list[dict], fields: list[str], rate: float = 0.20,
                             level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    """Converts a numeric amount field to a string with a currency prefix,
    simulating exports that don't strip formatting."""
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            if field in row and row[field] is not None and rng.random() < rate:
                row[field] = f"{rng.choice(CURRENCY_PREFIXES)}{row[field]}"
        out.append(row)
    return out


def inject_mixed_date_formats(rows: list[dict], field: str, rate: float = 0.15,
                               level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    """Reformats an ISO date string (YYYY-MM-DD) to MM/DD/YYYY for a subset
    of rows, simulating inconsistent exports within the same file."""
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        value = row.get(field)
        if value and isinstance(value, str) and rng.random() < rate:
            parts = value[:10].split("-")
            if len(parts) == 3:
                year, month, day = parts
                row[field] = f"{month}/{day}/{year}"
        out.append(row)
    return out


# -- CATEGORY: semantic conflicts -----------------------------------------

def flip_sign_convention(rows: list[dict], fields: list[str], rate: float = 0.30,
                          level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            if field in row and isinstance(row[field], (int, float)) and rng.random() < rate:
                row[field] = -row[field]
        out.append(row)
    return out


# -- CATEGORY: encoding problems -------------------------------------------

def inject_html_entities(rows: list[dict], fields: list[str], rate: float = 0.03,
                          level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            value = row.get(field)
            if isinstance(value, str) and rng.random() < rate:
                for char, entity in HTML_ENTITY_MAP.items():
                    value = value.replace(char, entity)
                row[field] = value
        out.append(row)
    return out


def inject_invisible_chars(rows: list[dict], fields: list[str], rate: float = 0.02,
                            level: float = 1.0, rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    rate = _rate(rate, level)
    out = []
    for row in rows:
        row = dict(row)
        for field in fields:
            value = row.get(field)
            if isinstance(value, str) and rng.random() < rate:
                pos = rng.randint(0, len(value))
                row[field] = value[:pos] + rng.choice(INVISIBLE_CHARS) + value[pos:]
        out.append(row)
    return out


def add_bom(filepath: Path) -> None:
    data = Path(filepath).read_bytes()
    if not data.startswith(b"\xef\xbb\xbf"):
        Path(filepath).write_bytes(b"\xef\xbb\xbf" + data)


def reencode_windows1252(filepath: Path) -> None:
    """Rewrites a UTF-8 text file as Windows-1252, dropping/mangling any
    characters that don't map (mirrors a real mis-encoded export)."""
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    path.write_bytes(text.encode("cp1252", errors="replace"))


def normalize_unicode_variant(value: str, rng: random.Random | None = None) -> str:
    """Occasionally returns an alternate (e.g. NFD) Unicode normal form of a
    string, simulating names captured through different input systems."""
    rng = rng or random.Random()
    return unicodedata.normalize(rng.choice(["NFC", "NFD"]), value)


# -- CATEGORY: schema drift (structural, applied at row-list level) -------

def add_unexpected_column(rows: list[dict], column: str, value_fn) -> list[dict]:
    return [dict(row, **{column: value_fn()}) for row in rows]


def drop_column(rows: list[dict], column: str) -> list[dict]:
    out = []
    for row in rows:
        row = dict(row)
        row.pop(column, None)
        out.append(row)
    return out


def reorder_columns(rows: list[dict], rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    out = []
    for row in rows:
        keys = list(row.keys())
        rng.shuffle(keys)
        out.append({k: row[k] for k in keys})
    return out


# -- file-level chaos (duplicate uploads, corruption, empty files) --------

def duplicate_file(filepath: Path, rng: random.Random | None = None) -> Path:
    """Copies a file under a different name, simulating a re-uploaded batch."""
    rng = rng or random.Random()
    path = Path(filepath)
    new_name = f"{path.stem}_copy{rng.randint(1, 999)}{path.suffix}"
    new_path = path.parent / new_name
    shutil.copyfile(path, new_path)
    return new_path


def truncate_file(filepath: Path, keep_fraction: float = 0.5) -> None:
    path = Path(filepath)
    data = path.read_bytes()
    path.write_bytes(data[: int(len(data) * keep_fraction)])


def empty_file(filepath: Path) -> None:
    Path(filepath).write_bytes(b"")
