from src.cleaning.unit_converter import convert_length, convert_weight


def test_convert_weight_lbs_to_kg():
    assert convert_weight(10, "lbs") == 4.5359


def test_convert_weight_oz_to_kg():
    assert convert_weight(16, "oz") == 0.4536


def test_convert_weight_kg_passthrough():
    assert convert_weight(5, "kg") == 5.0


def test_convert_weight_none_unit_uses_default():
    assert convert_weight(10, None) == convert_weight(10, "lbs")


def test_convert_weight_none_value_returns_none():
    assert convert_weight(None, "lbs") is None


def test_convert_weight_unknown_unit_raises():
    import pytest
    with pytest.raises(ValueError):
        convert_weight(10, "stone")


def test_convert_length_inches_to_cm():
    assert convert_length(1, "in") == 2.54


def test_convert_length_cm_passthrough():
    assert convert_length(10, "cm") == 10.0


def test_convert_length_none_value_returns_none():
    assert convert_length(None, "in") is None
