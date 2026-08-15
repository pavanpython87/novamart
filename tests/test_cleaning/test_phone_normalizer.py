from src.cleaning.phone_normalizer import normalize_phone


def test_normalize_phone_parens_format():
    assert normalize_phone("(415) 555-0132") == "+14155550132"


def test_normalize_phone_dashes_format():
    assert normalize_phone("415-555-0132") == "+14155550132"


def test_normalize_phone_no_separators():
    assert normalize_phone("4155550132") == "+14155550132"


def test_normalize_phone_with_country_code():
    assert normalize_phone("+1 415 555 0132") == "+14155550132"


def test_normalize_phone_none_returns_none():
    assert normalize_phone(None) is None


def test_normalize_phone_empty_string_returns_none():
    assert normalize_phone("") is None


def test_normalize_phone_invalid_returns_none():
    assert normalize_phone("not a phone number") is None
