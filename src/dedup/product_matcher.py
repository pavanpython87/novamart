"""Matches a source's ad-hoc product description (name/brand/category) back
to a canonical catalog product_id, for cases where SKU/ASIN mapping
(sku_mapper.py) can't resolve it directly.
"""

from __future__ import annotations

import pandas as pd

from src.dedup.match_scorer import token_set_ratio

NAME_WEIGHT = 0.6
BRAND_WEIGHT = 0.2
CATEGORY_WEIGHT = 0.2


def score_product_match(candidate: dict, catalog_row: dict) -> float:
    name_score = token_set_ratio(candidate.get("name"), catalog_row.get("name"))
    brand_score = 1.0 if (candidate.get("brand")
                           and candidate.get("brand") == catalog_row.get("brand")) else 0.0
    category_score = 1.0 if (candidate.get("category")
                              and candidate.get("category") == catalog_row.get("category")) else 0.0
    return round(NAME_WEIGHT * name_score + BRAND_WEIGHT * brand_score
                 + CATEGORY_WEIGHT * category_score, 4)


def best_match(candidate: dict, catalog_df: pd.DataFrame, threshold: float = 0.7) -> dict | None:
    best_row = None
    best_score = 0.0
    for row in catalog_df.to_dict("records"):
        score = score_product_match(candidate, row)
        if score > best_score:
            best_score = score
            best_row = row
    if best_row is None or best_score < threshold:
        return None
    return {"product_id": best_row["product_id"], "confidence": best_score}
