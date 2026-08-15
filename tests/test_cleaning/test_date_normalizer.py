from src.cleaning.date_normalizer import normalize_date


def test_normalize_date_mdy_slash():
    assert normalize_date("03/01/2024") == "2024-03-01"


def test_normalize_date_dmy_dash():
    assert normalize_date("01-03-2024", dayfirst=True) == "2024-03-01"


def test_normalize_date_month_name():
    assert normalize_date("March 1, 2024") == "2024-03-01"


def test_normalize_date_iso_date():
    assert normalize_date("2024-03-01") == "2024-03-01"


def test_normalize_date_iso_datetime_preserves_time():
    result = normalize_date("2024-03-01T10:30:00")
    assert result.startswith("2024-03-01T10:30:00")


def test_normalize_date_epoch_seconds():
    assert normalize_date(1709251200) == "2024-02-29" or normalize_date(1709251200) == "2024-03-01"


def test_normalize_date_epoch_seconds_as_string():
    assert normalize_date("1709251200") is not None


def test_normalize_date_none_returns_none():
    assert normalize_date(None) is None


def test_normalize_date_empty_string_returns_none():
    assert normalize_date("") is None


def test_normalize_date_unparseable_returns_none():
    assert normalize_date("not a date") is None
