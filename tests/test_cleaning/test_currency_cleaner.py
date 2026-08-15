from src.cleaning.currency_cleaner import clean_currency


def test_clean_currency_dollar_sign():
    assert clean_currency("$1,234.56") == 1234.56


def test_clean_currency_euro_sign():
    assert clean_currency("€99.99") == 99.99


def test_clean_currency_european_decimal_comma():
    assert clean_currency("1.234,56") == 1234.56


def test_clean_currency_plain_comma_decimal():
    assert clean_currency("99,50") == 99.5


def test_clean_currency_parenthesized_negative():
    assert clean_currency("($50.00)") == -50.0


def test_clean_currency_leading_minus():
    assert clean_currency("-$50.00") == -50.0


def test_clean_currency_plain_number():
    assert clean_currency("42.5") == 42.5


def test_clean_currency_none_returns_none():
    assert clean_currency(None) is None


def test_clean_currency_empty_string_returns_none():
    assert clean_currency("") is None


def test_clean_currency_unparseable_returns_none():
    assert clean_currency("abc") is None
