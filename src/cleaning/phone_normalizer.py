"""Normalizes phone numbers to E.164 format (e.g. +14155551234).

Source phone numbers arrive in 6+ formats across channels (parens, dashes,
dots, no separators, with/without country code); the phonenumbers library
handles the parsing ambiguity. Defaults to US as the assumed region for
numbers without an explicit country code, matching this pipeline's
customer base.
"""

from __future__ import annotations

import phonenumbers

DEFAULT_REGION = "US"


def normalize_phone(raw: str | None, region: str = DEFAULT_REGION) -> str | None:
    """Returns an E.164-formatted phone number, or None if raw is empty
    or can't be parsed into a valid number."""
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = phonenumbers.parse(str(raw), region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
