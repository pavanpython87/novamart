import pandas as pd

from src.dedup.customer_resolver import find_candidate_matches


def test_exact_email_match_auto_merges():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "email": "bob@x.com", "first_name": "Bob", "last_name": "Smith"},
        {"record_id": "2", "source": "amazon", "email": "bob@x.com", "first_name": "Robert", "last_name": "Smith"},
    ])
    matches = find_candidate_matches(records)
    assert len(matches) == 1
    assert matches[0]["confidence"] == 0.95
    assert matches[0]["action"] == "auto_merge"


def test_exact_phone_match_auto_merges():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "phone_e164": "+14155550132"},
        {"record_id": "2", "source": "pos", "phone_e164": "+14155550132"},
    ])
    matches = find_candidate_matches(records)
    assert len(matches) == 1
    assert matches[0]["confidence"] == 0.90
    assert matches[0]["action"] == "auto_merge"


def test_fuzzy_name_and_zip_match_flagged_for_review():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "first_name": "Robert", "last_name": "Smith",
         "postal_code": "94105"},
        {"record_id": "2", "source": "pos", "first_name": "Robert", "last_name": "Smyth",
         "postal_code": "94105"},
    ])
    matches = find_candidate_matches(records)
    assert len(matches) == 1
    assert matches[0]["confidence"] == 0.75
    assert matches[0]["action"] == "review"


def test_same_source_pairs_are_never_compared():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "email": "bob@x.com"},
        {"record_id": "2", "source": "shopify", "email": "bob@x.com"},
    ])
    matches = find_candidate_matches(records)
    assert matches == []


def test_no_match_returns_empty_list():
    records = pd.DataFrame([
        {"record_id": "1", "source": "shopify", "first_name": "Alice", "last_name": "Jones",
         "postal_code": "10001"},
        {"record_id": "2", "source": "amazon", "first_name": "Zach", "last_name": "Young",
         "postal_code": "90210"},
    ])
    matches = find_candidate_matches(records)
    assert matches == []
