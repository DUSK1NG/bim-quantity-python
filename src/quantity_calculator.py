"""Select and calculate traceable quantities for cleaned element rows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config_loader import ProjectConfig


@dataclass(frozen=True)
class QuantityResult:
    """Quantity table plus the fixed rules used to calculate it."""

    frame: pd.DataFrame
    calculation_notes: tuple[str, ...]


_SUPPORTED_CATEGORIES = frozenset({"Beam", "Column", "Slab", "Wall", "Door", "Window"})
_VOLUME_CATEGORIES = frozenset({"Column", "Slab", "Wall"})
_COUNT_CATEGORIES = frozenset({"Door", "Window"})

_CALCULATION_NOTES: tuple[str, ...] = (
    "有限非负 quantity 优先保留；IFC BaseQuantity 来源优先级最高。",
    "Beam 使用 length_m 计算，单位为 m。",
    "Column、Slab、Wall 使用 volume_m3 计算，单位为 m³。",
    "Door、Window 使用已有 quantity 计算，单位为 樘。",
    "缺少有效工程量或尺寸时保持空值，来源为 Missing。",
)


def _is_missing(value: Any) -> bool:
    """Return whether a scalar value is a pandas-style missing value."""

    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(missing)
    except (TypeError, ValueError):
        # Non-scalar values are outside the row contract and are not treated
        # as missing here; the numeric conversion helper will reject them.
        return False


def _finite_nonnegative(value: Any) -> float | None:
    """Convert one scalar to a finite non-negative number when possible."""

    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _category_for_row(row: pd.Series, config: ProjectConfig) -> Any:
    """Use a cleaned category, with an IFC mapping fallback for sparse inputs."""

    category = row.get("category")
    if not _is_missing(category):
        return category
    ifc_class = row.get("ifc_class")
    if _is_missing(ifc_class):
        return category
    try:
        return config.category_mapping["ifc_class_to_category"].get(ifc_class, category)
    except (AttributeError, KeyError, TypeError):
        return category


def calculate_quantities(frame: pd.DataFrame, config: ProjectConfig) -> QuantityResult:
    """Calculate quantities without mutating ``frame``.

    Valid existing quantities are retained as schedule observations, except an
    explicit ``IFC BaseQuantity`` source is retained verbatim.  Missing values
    are filled only by the six category-specific rules documented in the
    stage-3.2 contract.  Invalid existing values are left in place for later
    quality reporting and are never replaced by a dimension estimate.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    result = frame.copy(deep=True)
    for column in ("quantity", "unit", "quantity_source"):
        if column not in result.columns:
            result[column] = pd.NA

    quantities = result["quantity"].tolist()
    units = result["unit"].tolist()
    sources = result["quantity_source"].tolist()

    for position, (_, row) in enumerate(result.iterrows()):
        original_quantity = quantities[position]
        valid_quantity = _finite_nonnegative(original_quantity)
        category = _category_for_row(row, config)

        if valid_quantity is not None:
            quantities[position] = valid_quantity
            if not _is_missing(sources[position]) and sources[position] == "IFC BaseQuantity":
                # The IFC source is authoritative when its value is valid.
                sources[position] = "IFC BaseQuantity"
            else:
                sources[position] = "CSV Schedule"
            if category in _COUNT_CATEGORIES:
                units[position] = "樘"
            continue

        # A present but invalid quantity (negative, infinite, or non-numeric)
        # remains visible for the quality checker; dimensions must not replace it.
        if not _is_missing(original_quantity):
            sources[position] = "Missing"
            continue

        calculated: float | None = None
        calculated_unit: str | None = None
        if category == "Beam":
            calculated = _finite_nonnegative(row.get("length_m"))
            calculated_unit = "m"
        elif category in _VOLUME_CATEGORIES:
            calculated = _finite_nonnegative(row.get("volume_m3"))
            calculated_unit = "m³"
        elif category in _COUNT_CATEGORIES:
            # Doors and windows have no dimension-derived count formula.  A
            # valid existing quantity is handled by the branch above.
            calculated = None
            calculated_unit = "樘"

        if category in _SUPPORTED_CATEGORIES and calculated is not None:
            quantities[position] = calculated
            units[position] = calculated_unit
            sources[position] = "Parameter Calculation"
        else:
            quantities[position] = pd.NA
            units[position] = pd.NA
            sources[position] = "Missing"

    result["quantity"] = quantities
    result["unit"] = units
    result["quantity_source"] = sources
    return QuantityResult(frame=result, calculation_notes=_CALCULATION_NOTES)


__all__ = ["QuantityResult", "calculate_quantities"]
