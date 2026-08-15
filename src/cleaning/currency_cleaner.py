"""Strips currency symbols and thousands separators, handling both
US-style (1,234.56) and European-style (1.234,56) decimal conventions,
plus parenthesized/leading-minus negatives.
"""

from __future__ import annotations

import re

CURRENCY_SYMBOLS = re.compile(r"[$€£¥₹]")


def clean_currency(raw) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = CURRENCY_SYMBOLS.sub("", text).strip()
    if text.startswith("-"):
        negative = True
        text = text[1:]

    if "," in text and "." in text:
        # Whichever separator appears last is the decimal point.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            text = text.replace(",", ".")  # European decimal comma
        else:
            text = text.replace(",", "")   # thousands separator

    try:
        value = float(text)
    except ValueError:
        return None
    return -value if negative else value
