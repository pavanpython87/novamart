"""Converts weight and dimension measurements to canonical units:
weight -> kilograms, length/dimensions -> centimeters.
"""

from __future__ import annotations

_WEIGHT_TO_KG = {
    "kg": 1.0,
    "lbs": 0.45359237,
    "lb": 0.45359237,
    "oz": 0.028349523125,
    "g": 0.001,
}
_LENGTH_TO_CM = {
    "cm": 1.0,
    "in": 2.54,
    "inch": 2.54,
    "inches": 2.54,
    "mm": 0.1,
    "m": 100.0,
}


def convert_weight(value: float | None, unit: str | None, default_unit: str = "lbs") -> float | None:
    if value is None:
        return None
    unit_key = (unit or default_unit).strip().lower()
    factor = _WEIGHT_TO_KG.get(unit_key)
    if factor is None:
        raise ValueError(f"Unknown weight unit: {unit}")
    return round(value * factor, 4)


def convert_length(value: float | None, unit: str | None, default_unit: str = "in") -> float | None:
    if value is None:
        return None
    unit_key = (unit or default_unit).strip().lower()
    factor = _LENGTH_TO_CM.get(unit_key)
    if factor is None:
        raise ValueError(f"Unknown length unit: {unit}")
    return round(value * factor, 4)
