"""Standardizes address components: consistent street-suffix/unit
abbreviations and casing. Operates on the {line1, line2, city, region,
postal_code, country} address dict shape produced by the simulator (and,
by extension, what identity data is normalized to across all sources).
"""

from __future__ import annotations

import re

STREET_ABBREVIATIONS = {
    "street": "St", "avenue": "Ave", "boulevard": "Blvd", "drive": "Dr",
    "lane": "Ln", "road": "Rd", "court": "Ct", "place": "Pl", "square": "Sq",
    "terrace": "Ter", "circle": "Cir", "highway": "Hwy", "parkway": "Pkwy",
    "trail": "Trl", "way": "Way",
}
UNIT_ABBREVIATIONS = {
    "apartment": "Apt", "suite": "Ste", "unit": "Unit", "building": "Bldg",
    "floor": "Fl", "room": "Rm",
}

_WORD_RE = re.compile(r"[A-Za-z']+")


def _replace_words(text: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        return mapping.get(match.group(0).lower(), match.group(0))
    return _WORD_RE.sub(repl, text)


def standardize_line(line: str | None) -> str:
    if not line:
        return ""
    line = line.strip()
    line = _replace_words(line, STREET_ABBREVIATIONS)
    line = _replace_words(line, UNIT_ABBREVIATIONS)
    return line


def standardize_address(address: dict) -> dict:
    return {
        "line1": standardize_line(address.get("line1")),
        "line2": standardize_line(address.get("line2")),
        "city": (address.get("city") or "").strip().title(),
        "region": (address.get("region") or "").strip().upper(),
        "postal_code": (address.get("postal_code") or "").strip().upper(),
        "country": (address.get("country") or "").strip().upper(),
    }
