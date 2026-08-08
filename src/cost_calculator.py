"""Match teaching unit prices and calculate traceable total costs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config_loader import ProjectConfig
from src.quality_report import DISCLAIMER
from src.schema import STANDARD_COLUMNS


_COST_COLUMNS: tuple[str, ...] = tuple(
    column for column in STANDARD_COLUMNS if column in {"unit_price", "total_cost"}
)


@dataclass(frozen=True)
class CostResult:
    """Cost table and raw row numbers that could not be priced."""

    frame: pd.DataFrame
    unmatched_rows: tuple[int, ...]


def _is_missing(value: Any) -> bool:
    """Return whether a scalar is missing according to pandas semantics."""

    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(missing)
    except (TypeError, ValueError):
        return False


def _same_value(left: Any, right: Any) -> bool:
    """Compare two scalar key values without propagating ``pd.NA``."""

    if _is_missing(left) or _is_missing(right):
        return _is_missing(left) and _is_missing(right)
    try:
        equal = left == right
        return bool(equal)
    except (TypeError, ValueError):
        return False


def _is_fallback_material(value: Any) -> bool:
    """Identify an explicitly configured category/unit fallback row.

    The CSV contract keeps a ``material`` column, so an empty material cell is
    the canonical way to express a fallback.  A few readable markers are also
    accepted for hand-built teaching configurations; ordinary material names
    (including ``未知材料``) never act as fallbacks.
    """

    if _is_missing(value):
        return True
    if not isinstance(value, str):
        return False
    return value.strip().casefold() in {"", "*", "any", "default", "默认", "兜底"}


def _finite_nonnegative(value: Any) -> float | None:
    """Convert a quantity to a finite non-negative float when possible."""

    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _finite_price(value: Any) -> float | None:
    """Convert one configured price to a finite float."""

    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _raw_row_number(row: pd.Series, position: int) -> int:
    """Return a stable integer row number, falling back to one-based position."""

    if "raw_row_number" in row:
        value = row.get("raw_row_number")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            number = math.nan
        if math.isfinite(number) and number.is_integer():
            return int(number)
    return position + 1


def _find_price(
    row: pd.Series,
    prices: pd.DataFrame,
) -> float | None:
    """Find one exact price, then one explicit category/unit fallback price."""

    category = row.get("category")
    material = row.get("material")
    unit = row.get("unit")

    # The first lookup is deliberately row-wise and exact.  In particular,
    # no case folding, substring matching, or material guessing is performed.
    exact: list[Any] = []
    for _, price_row in prices.iterrows():
        if (
            _same_value(price_row["category"], category)
            and _same_value(price_row["material"], material)
            and _same_value(price_row["unit"], unit)
        ):
            exact.append(price_row["unit_price"])
    if exact:
        return _finite_price(exact[0])

    # A fallback is valid only when the configuration itself marks a row as
    # material-independent.  Regular rows such as Beam/混凝土/m³ must never
    # become a fallback for an unknown material.
    fallback: list[Any] = []
    for _, price_row in prices.iterrows():
        if (
            _same_value(price_row["category"], category)
            and _same_value(price_row["unit"], unit)
            and _is_fallback_material(price_row["material"])
        ):
            fallback.append(price_row["unit_price"])
    if len(fallback) == 1:
        return _finite_price(fallback[0])
    return None


def calculate_costs(frame: pd.DataFrame, config: ProjectConfig) -> CostResult:
    """Calculate total costs from exact teaching-price matches.

    The input is copied before any columns are updated.  Rows without an exact
    price (or without a finite non-negative quantity) retain missing
    ``unit_price`` and ``total_cost`` values and are listed by raw row number.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    prices = config.unit_prices
    required_price_columns = {"category", "material", "unit", "unit_price"}
    if not required_price_columns.issubset(prices.columns):
        missing = ", ".join(sorted(required_price_columns - set(prices.columns)))
        raise ValueError(f"config.unit_prices 缺少列: {missing}")

    result = frame.copy(deep=True)
    for column in _COST_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    matched_prices: list[float | None] = []
    totals: list[float | None] = []
    unmatched: list[int] = []

    for position, (index, row) in enumerate(result.iterrows()):
        quantity = _finite_nonnegative(row.get("quantity"))
        unit_price = _find_price(row, prices)
        if quantity is None or unit_price is None:
            matched_prices.append(None)
            totals.append(None)
            unmatched.append(_raw_row_number(row, position))
            continue

        try:
            total = quantity * unit_price
        except (OverflowError, TypeError):
            total = math.nan
        if not math.isfinite(total) or total < 0:
            matched_prices.append(None)
            totals.append(None)
            unmatched.append(_raw_row_number(row, position))
            continue

        matched_prices.append(unit_price)
        totals.append(total)

    result["unit_price"] = pd.Series(matched_prices, index=result.index, dtype="Float64")
    result["total_cost"] = pd.Series(totals, index=result.index, dtype="Float64")

    field_order = tuple(config.field_mapping["field_order"])
    for column in field_order:
        if column not in result.columns:
            result[column] = pd.NA
    extra_columns = [column for column in result.columns if column not in field_order]
    result = result.loc[:, [*field_order, *extra_columns]]
    return CostResult(frame=result, unmatched_rows=tuple(unmatched))


__all__ = ["DISCLAIMER", "CostResult", "calculate_costs"]
