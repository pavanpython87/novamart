import pandas as pd

from src.dedup.product_matcher import best_match, score_product_match


def test_score_product_match_identical_fields():
    candidate = {"name": "Wireless Mouse", "brand": "Logitech", "category": "Computing"}
    catalog_row = {"name": "Wireless Mouse", "brand": "Logitech", "category": "Computing"}
    assert score_product_match(candidate, catalog_row) == 1.0


def test_score_product_match_name_only():
    candidate = {"name": "Wireless Mouse", "brand": "Acme", "category": "Audio"}
    catalog_row = {"name": "Wireless Mouse", "brand": "Logitech", "category": "Computing"}
    assert score_product_match(candidate, catalog_row) == 0.6


def test_best_match_returns_highest_scoring_row():
    catalog = pd.DataFrame([
        {"product_id": "PROD-1", "name": "Wireless Mouse", "brand": "Logitech", "category": "Computing"},
        {"product_id": "PROD-2", "name": "Bluetooth Speaker", "brand": "Sony", "category": "Audio"},
    ])
    candidate = {"name": "Wireless Mouse", "brand": "Logitech", "category": "Computing"}
    result = best_match(candidate, catalog)
    assert result["product_id"] == "PROD-1"
    assert result["confidence"] == 1.0


def test_best_match_below_threshold_returns_none():
    catalog = pd.DataFrame([
        {"product_id": "PROD-1", "name": "Bluetooth Speaker", "brand": "Sony", "category": "Audio"},
    ])
    candidate = {"name": "Totally Different Item", "brand": "Nobody", "category": "Gaming"}
    result = best_match(candidate, catalog)
    assert result is None
