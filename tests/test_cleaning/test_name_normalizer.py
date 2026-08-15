from src.cleaning.name_normalizer import normalize_name


def test_normalize_name_all_caps():
    assert normalize_name("ROBERT SMITH") == "Robert Smith"


def test_normalize_name_all_lowercase():
    assert normalize_name("robert smith") == "Robert Smith"


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Robert   Smith  ") == "Robert Smith"


def test_normalize_name_hyphenated():
    assert normalize_name("mary-jane watson") == "Mary-Jane Watson"


def test_normalize_name_apostrophe():
    assert normalize_name("o'brien") == "O'Brien"


def test_normalize_name_none_returns_empty_string():
    assert normalize_name(None) == ""


def test_normalize_name_empty_string_returns_empty_string():
    assert normalize_name("") == ""
