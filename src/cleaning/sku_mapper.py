"""Maps cross-channel SKU identifiers (Shopify SKU, Amazon ASIN, POS
internal SKU) to a single unified product_id, using the product catalog
as the source of truth and config/sku_mapping.yaml's manual_overrides for
edge cases the catalog doesn't resolve.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

DEFAULT_MAPPING_CONFIG = Path("config/sku_mapping.yaml")


class SKUMapper:
    def __init__(self, catalog_df: pd.DataFrame,
                 mapping_config_path: str | Path = DEFAULT_MAPPING_CONFIG):
        self._by_shopify: dict[str, str] = {}
        self._by_amazon: dict[str, str] = {}
        self._by_pos: dict[str, str] = {}
        self._load_catalog(catalog_df)
        self._load_manual_overrides(mapping_config_path)

    def _load_catalog(self, catalog_df: pd.DataFrame) -> None:
        for row in catalog_df.to_dict("records"):
            product_id = row.get("product_id")
            if not product_id:
                continue
            if row.get("shopify_sku"):
                self._by_shopify[str(row["shopify_sku"])] = product_id
            if row.get("amazon_asin"):
                self._by_amazon[str(row["amazon_asin"])] = product_id
            if row.get("pos_internal_sku"):
                self._by_pos[str(row["pos_internal_sku"])] = product_id

    def _load_manual_overrides(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for override in raw.get("manual_overrides") or []:
            product_id = override.get("unified_product_id")
            if not product_id:
                continue
            if override.get("shopify_sku"):
                self._by_shopify[override["shopify_sku"]] = product_id
            if override.get("amazon_asin"):
                self._by_amazon[override["amazon_asin"]] = product_id
            if override.get("pos_internal_sku"):
                self._by_pos[override["pos_internal_sku"]] = product_id

    def map_shopify(self, sku: str | None) -> str | None:
        return self._by_shopify.get(sku) if sku else None

    def map_amazon(self, asin: str | None) -> str | None:
        return self._by_amazon.get(asin) if asin else None

    def map_pos(self, internal_sku: str | None) -> str | None:
        return self._by_pos.get(internal_sku) if internal_sku else None
