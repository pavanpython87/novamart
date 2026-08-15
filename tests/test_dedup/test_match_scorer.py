from src.dedup.match_scorer import (
    jaro_winkler_similarity,
    levenshtein_similarity,
    token_set_ratio,
)


def test_jaro_winkler_identical_strings():
    assert jaro_winkler_similarity("Robert Smith", "Robert Smith") == 1.0


def test_jaro_winkler_similar_strings_high_score():
    assert jaro_winkler_similarity("Robert Smith", "Robert Smyth") > 0.85


def test_jaro_winkler_empty_returns_zero():
    assert jaro_winkler_similarity("", "Robert") == 0.0
    assert jaro_winkler_similarity(None, "Robert") == 0.0


def test_levenshtein_identical_strings():
    assert levenshtein_similarity("abc", "abc") == 1.0


def test_levenshtein_different_strings_lower_score():
    assert levenshtein_similarity("abc", "xyz") < 0.5


def test_token_set_ratio_reordered_tokens_high_score():
    assert token_set_ratio("Wireless Bluetooth Headphones", "Headphones Bluetooth Wireless") == 1.0


def test_token_set_ratio_empty_returns_zero():
    assert token_set_ratio("", "x") == 0.0
