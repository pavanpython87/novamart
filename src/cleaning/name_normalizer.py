"""Normalizes person names: trims/collapses whitespace, Unicode-normalizes
accented characters (NFC), and applies consistent title casing so the same
person's name compares equal regardless of source-specific casing quirks
(ALL CAPS exports, all-lowercase form fields, etc.).
"""

from __future__ import annotations

import unicodedata


def normalize_name(raw: str | None) -> str:
    if not raw:
        return ""
    text = unicodedata.normalize("NFC", raw.strip())
    text = " ".join(text.split())
    return text.title()
