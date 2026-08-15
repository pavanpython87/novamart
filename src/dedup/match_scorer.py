"""Fuzzy string similarity scorers built on rapidfuzz: Jaro-Winkler,
Levenshtein, and token-set ratio, all normalized to 0.0-1.0. Used by
customer_resolver.py and product_matcher.py to score candidate matches.
"""

from __future__ import annotations

from rapidfuzz import distance, fuzz


def jaro_winkler_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return distance.JaroWinkler.similarity(a, b)


def levenshtein_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return distance.Levenshtein.normalized_similarity(a, b)


def token_set_ratio(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0
