"""Deterministic quantity, cost and project-overview aggregations."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.quality_report import DISCLAIMER, QualityReport


_SUMMARY_METRICS: tuple[str, ...] = (
    "element_count",
    "quantity_sum",
    "area_sum",
    "volume_sum",
    "total_cost",
)
_NUMERIC_COLUMNS: tuple[str, ...] = ("quantity", "area_m2", "volume_m3", "total_cost")
_SUMMARY_SUFFIXES: dict[str, str] = {
    "quantity": "quantity_sum",
    "area_m2": "area_sum",
    "volume_m3": "volume_sum",
    "total_cost": "total_cost",
}
_COST_GROUP_FIELDS: tuple[str, ...] = ("category", "material", "unit")


def _is_missing(value: Any) -> bool:
    """Return whether a scalar has pandas-style missing semantics."""

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


def _finite_nonnegative(value: Any) -> float | None:
    """Convert a scalar to a finite non-negative float, otherwise ``None``."""

    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _display_group(value: Any) -> Any:
    """Use a stable Chinese label for missing grouping values."""

    if _is_missing(value):
        return "未分类"
    if isinstance(value, str) and not value.strip():
        return "未分类"
    return value


def _canonical_identifier(value: Any) -> Any:
    """Return a non-empty identifier suitable for unique element counts."""

    if _is_missing(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    try:
        hash(value)
    except TypeError:
        return str(value).strip() or None
    return value


def _basename(source_file: str | Path) -> str:
    """Return a platform-neutral source basename for report metadata."""

    normalized = str(source_file).replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _valid_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return one numeric series containing only finite non-negative values."""

    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    values = [_finite_nonnegative(value) for value in frame[column].tolist()]
    return pd.Series(values, index=frame.index, dtype="Float64")


def _valid_id_series(frame: pd.DataFrame) -> pd.Series:
    """Return canonical IDs while keeping missing IDs out of counts."""

    if "element_id" not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="object")
    values = [_canonical_identifier(value) for value in frame["element_id"].tolist()]
    return pd.Series(values, index=frame.index, dtype="object")


def _empty_summary(group_fields: tuple[str, ...]) -> pd.DataFrame:
    """Return an empty summary with the same columns as a populated result."""

    return pd.DataFrame(columns=[*group_fields, *_SUMMARY_METRICS])


def _summarize(frame: pd.DataFrame, group_fields: tuple[str, ...]) -> pd.DataFrame:
    """Build one deterministic grouped summary for the requested fields."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    working = frame.copy(deep=True)
    for field in group_fields:
        if field not in working.columns:
            working[field] = "未分类"
        else:
            working[field] = working[field].map(_display_group)
    working["_valid_element_id"] = _valid_id_series(working)
    for column in _NUMERIC_COLUMNS:
        working[f"_{column}"] = _valid_numeric_series(working, column)

    if working.empty:
        return _empty_summary(group_fields)

    grouped = working.groupby(list(group_fields), dropna=False, sort=True)

    aggregations: dict[str, tuple[str, Callable[[pd.Series], Any]]] = {
        "element_count": (
            "_valid_element_id",
            lambda values: int(values.dropna().nunique()),
        )
    }
    for source_column, output_column in _SUMMARY_SUFFIXES.items():
        aggregations[output_column] = (
            f"_{source_column}",
            lambda values: values.sum(min_count=1),
        )
    result = grouped.agg(**aggregations).reset_index()
    return result.loc[:, [*group_fields, *_SUMMARY_METRICS]]


def summarize_by_level(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize valid quantities, dimensions and costs by level."""

    return _summarize(frame, ("level",))


def summarize_by_category(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize valid quantities, dimensions and costs by category."""

    return _summarize(frame, ("category",))


def summarize_by_material(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize valid quantities, dimensions and costs by material."""

    return _summarize(frame, ("material",))


def summarize_costs(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize valid amounts by category, material and unit."""

    return _summarize(frame, _COST_GROUP_FIELDS)


def _unique_nonmissing_count(frame: pd.DataFrame, column: str) -> int:
    """Count distinct non-empty values in a frame column."""

    if column not in frame.columns:
        return 0
    values = [_canonical_identifier(value) for value in frame[column].tolist()]
    return int(pd.Series(values, dtype="object").dropna().nunique())


def _valid_sum(frame: pd.DataFrame, column: str) -> float | None:
    """Sum finite non-negative values, leaving an all-missing total as null."""

    values = _valid_numeric_series(frame, column)
    total = values.sum(min_count=1)
    if _is_missing(total):
        return None
    return float(total)


def build_overview(
    frame: pd.DataFrame,
    report: QualityReport,
    source_file: str,
) -> dict[str, Any]:
    """Build the stable project overview consumed by reports and pipeline code."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if not isinstance(report, QualityReport):
        raise TypeError("report must be a QualityReport")

    return {
        "source_file": _basename(source_file),
        "total_rows": int(len(frame)),
        "element_count": _unique_nonmissing_count(frame, "element_id"),
        "category_count": _unique_nonmissing_count(frame, "category"),
        "level_count": _unique_nonmissing_count(frame, "level"),
        "area_sum": _valid_sum(frame, "area_m2"),
        "volume_sum": _valid_sum(frame, "volume_m3"),
        "issue_rows": int(report.issue_rows),
        "total_cost": _valid_sum(frame, "total_cost"),
        "disclaimer": DISCLAIMER,
    }


__all__ = [
    "build_overview",
    "summarize_by_category",
    "summarize_by_level",
    "summarize_by_material",
    "summarize_costs",
]
