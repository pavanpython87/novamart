import pandas as pd

from src.cleaning.sku_mapper import SKUMapper


def test_sku_mapper_resolves_from_catalog(tmp_path):
    catalog = pd.DataFrame({
        "product_id": ["PROD-000001"],
        "shopify_sku": ["SH-1234"],
        "amazon_asin": ["B00ABC1234"],
        "pos_internal_sku": ["POS-9981"],
    })
    empty_config = tmp_path / "sku_mapping.yaml"
    empty_config.write_text("manual_overrides: []\n")
    mapper = SKUMapper(catalog, empty_config)
    assert mapper.map_shopify("SH-1234") == "PROD-000001"
    assert mapper.map_amazon("B00ABC1234") == "PROD-000001"
    assert mapper.map_pos("POS-9981") == "PROD-000001"


def test_sku_mapper_unknown_sku_returns_none(tmp_path):
    catalog = pd.DataFrame({"product_id": ["PROD-1"], "shopify_sku": ["SH-1"],
                             "amazon_asin": [None], "pos_internal_sku": [None]})
    config = tmp_path / "sku_mapping.yaml"
    config.write_text("manual_overrides: []\n")
    mapper = SKUMapper(catalog, config)
    assert mapper.map_shopify("SH-UNKNOWN") is None
    assert mapper.map_shopify(None) is None


def test_sku_mapper_manual_override_takes_precedence(tmp_path):
    catalog = pd.DataFrame({"product_id": ["PROD-1"], "shopify_sku": ["SH-1"],
                             "amazon_asin": [None], "pos_internal_sku": [None]})
    config = tmp_path / "sku_mapping.yaml"
    config.write_text(
        "manual_overrides:\n"
        "  - shopify_sku: SH-1\n"
        "    unified_product_id: PROD-OVERRIDE\n"
    )
    mapper = SKUMapper(catalog, config)
    assert mapper.map_shopify("SH-1") == "PROD-OVERRIDE"


def test_sku_mapper_missing_config_file_is_tolerated(tmp_path):
    catalog = pd.DataFrame({"product_id": ["PROD-1"], "shopify_sku": ["SH-1"],
                             "amazon_asin": [None], "pos_internal_sku": [None]})
    mapper = SKUMapper(catalog, tmp_path / "does_not_exist.yaml")
    assert mapper.map_shopify("SH-1") == "PROD-1"
