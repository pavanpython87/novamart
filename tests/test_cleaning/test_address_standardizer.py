from src.cleaning.address_standardizer import standardize_address, standardize_line


def test_standardize_line_abbreviates_street_suffix():
    assert standardize_line("123 Main Street") == "123 Main St"


def test_standardize_line_abbreviates_unit():
    assert standardize_line("Apartment 4B") == "Apt 4B"


def test_standardize_line_empty_returns_empty_string():
    assert standardize_line(None) == ""
    assert standardize_line("") == ""


def test_standardize_address_full_dict():
    address = {
        "line1": "456 Oak Avenue",
        "line2": "suite 200",
        "city": "san francisco",
        "region": "ca",
        "postal_code": "94105",
        "country": "us",
    }
    result = standardize_address(address)
    assert result["line1"] == "456 Oak Ave"
    assert result["line2"] == "Ste 200"
    assert result["city"] == "San Francisco"
    assert result["region"] == "CA"
    assert result["country"] == "US"
