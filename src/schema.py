"""Stable data contracts for the BIM quantity foundation.

This module deliberately contains only schema definitions and validation.  It
does not read project configuration files or import optional IFC libraries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


STANDARD_COLUMNS: tuple[str, ...] = (
    "element_id",
    "guid",
    "source",
    "ifc_class",
    "category",
    "element_name",
    "type_name",
    "level",
    "material",
    "length_m",
    "area_m2",
    "volume_m3",
    "quantity",
    "unit",
    "unit_price",
    "total_cost",
    "quantity_source",
    "quality_status",
)

QUANTITY_SOURCES: tuple[str, ...] = (
    "IFC BaseQuantity",
    "Parameter Calculation",
    "CSV Schedule",
    "Missing",
)

QUALITY_STATUSES: tuple[str, ...] = ("Pass", "Warning", "Error")

IFC_CLASSES: tuple[str, ...] = (
    "IfcBeam",
    "IfcColumn",
    "IfcSlab",
    "IfcWall",
    "IfcDoor",
    "IfcWindow",
)

LEVELS: tuple[str, ...] = ("一层", "二层", "三层")
UNITS: tuple[str, ...] = ("m", "m²", "m³", "个", "樘")


@dataclass(frozen=True)
class SampleDataSpec:
    """Defaults used by the deterministic sample-data generator."""

    seed: int = 20260804
    rows: int = 240
    levels: tuple[str, ...] = LEVELS
    ifc_classes: tuple[str, ...] = IFC_CLASSES
    exception_counts: dict[str, int] = field(
        default_factory=lambda: {
            "missing_material": 5,
            "missing_level": 3,
            "duplicate_guid_groups": 2,
            "zero_volume": 4,
            "invalid_name": 3,
            "invalid_unit": 2,
            "unmatched_unit_price": 2,
        }
    )


@dataclass(frozen=True)
class SchemaValidationResult:
    """Result of validating a DataFrame against the standard schema."""

    valid: bool
    missing_columns: tuple[str, ...] = ()
    invalid_enum_values: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    messages: tuple[str, ...] = ()


def _invalid_values(frame: pd.DataFrame, column: str, allowed: tuple[str, ...]) -> tuple[Any, ...]:
    """Return distinct, deterministic values not present in an enum.

    Values are kept as their original objects for diagnostics.  String values
    are sorted for readable output; mixed or otherwise unorderable values use
    their string representation as a stable fallback.
    """

    values = {value for value in frame[column].dropna() if value not in allowed}
    try:
        return tuple(sorted(values))
    except TypeError:
        return tuple(sorted(values, key=str))


def validate_standard_dataframe(frame: pd.DataFrame) -> SchemaValidationResult:
    """Validate required columns and enum fields in a standard DataFrame.

    Missing columns and unknown enum values are reported together so a
    beginner can fix all visible schema issues in one run. Empty values are
    allowed at this layer; row-level quality rules belong to later modules.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    missing = tuple(column for column in STANDARD_COLUMNS if column not in frame.columns)
    invalid: dict[str, tuple[Any, ...]] = {}

    if "quantity_source" in frame.columns:
        values = _invalid_values(frame, "quantity_source", QUANTITY_SOURCES)
        if values:
            invalid["quantity_source"] = values

    if "quality_status" in frame.columns:
        values = _invalid_values(frame, "quality_status", QUALITY_STATUSES)
        if values:
            invalid["quality_status"] = values

    messages = tuple(f"missing required column: {name}" for name in missing)
    messages += tuple(
        f"invalid {name} values: {values}" for name, values in invalid.items()
    )

    return SchemaValidationResult(
        valid=not missing and not invalid,
        missing_columns=missing,
        invalid_enum_values=invalid,
        messages=messages,
    )
