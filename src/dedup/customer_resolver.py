"""Cross-channel customer entity resolution.

Confidence rules (PROJECT_PLAN.md 5.5):
  1. Exact match on email               -> confidence 0.95
  2. Exact match on E.164 phone         -> confidence 0.90
  3. Fuzzy: normalized name similarity > 0.85 AND
     (same postal code OR same address line) -> confidence 0.75

Outcome by confidence:
  >= 0.90              -> auto_merge
  0.70 <= score < 0.90  -> review
  < 0.70                -> not returned (treated as separate customers)

Records are expected to already be cleaned (name_normalizer,
phone_normalizer, address_standardizer applied) before being passed in.
Only cross-source pairs are compared — same-source duplicates are
order_deduplicator's job, not entity resolution's.
"""

from __future__ import annotations

from itertools import combinations

import pandas as pd

from src.dedup.match_scorer import jaro_winkler_similarity

AUTO_MERGE_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.70
NAME_SIMILARITY_THRESHOLD = 0.85


def _score_pair(a: dict, b: dict) -> tuple[float, str] | None:
    if a.get("email") and b.get("email") and a["email"] == b["email"]:
        return 0.95, "exact_email"
    if a.get("phone_e164") and b.get("phone_e164") and a["phone_e164"] == b["phone_e164"]:
        return 0.90, "exact_phone"

    name_a = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
    name_b = f"{b.get('first_name', '')} {b.get('last_name', '')}".strip()
    name_score = jaro_winkler_similarity(name_a, name_b)
    same_zip = bool(a.get("postal_code")) and a.get("postal_code") == b.get("postal_code")
    same_address = bool(a.get("address_line1")) and a.get("address_line1") == b.get("address_line1")
    if name_score > NAME_SIMILARITY_THRESHOLD and (same_zip or same_address):
        return 0.75, "fuzzy_name_address"
    return None


def find_candidate_matches(records: pd.DataFrame) -> list[dict]:
    """Returns match candidates (confidence >= REVIEW_THRESHOLD) between
    every cross-source pair of records."""
    candidates = []
    rows = records.to_dict("records")
    for a, b in combinations(rows, 2):
        if a.get("source") == b.get("source"):
            continue
        result = _score_pair(a, b)
        if result is None:
            continue
        score, match_type = result
        action = "auto_merge" if score >= AUTO_MERGE_THRESHOLD else "review"
        candidates.append({
            "record_id_a": a.get("record_id"), "record_id_b": b.get("record_id"),
            "source_a": a.get("source"), "source_b": b.get("source"),
            "confidence": score, "match_type": match_type, "action": action,
        })
    return candidates
