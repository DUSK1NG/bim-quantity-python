"""Small, side-effect-free view filters shared by dashboard pages.

The pages receive already-calculated pipeline artifacts.  These helpers only
select rows for display; they intentionally do not calculate quantities,
costs, quality rules, or validation metrics.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd


def _values(values: Iterable[Any] | None) -> tuple[Any, ...]:
    """Normalize a multiselect value while treating an empty selection as all."""

    if values is None:
        return ()
    result: list[Any] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() in {"", "全部", "(全部)"}:
            continue
        result.append(value)
    return tuple(result)


def _isin(frame: pd.DataFrame, column: str, values: tuple[Any, ...]) -> pd.Series:
    """Build a safe membership mask for a possibly sparse view frame."""

    if not values:
        return pd.Series(True, index=frame.index)
    if column not in frame.columns:
        # A grouped summary only exposes its own dimensions (for example,
        # ``by_level`` has no material column).  A filter for another
        # dimension therefore cannot be applied here and should not make a
        # useful summary disappear.
        return pd.Series(True, index=frame.index)
    return frame[column].isin(values)


def filter_summary(
    frame: pd.DataFrame,
    *,
    levels: Iterable[Any] | None = None,
    categories: Iterable[Any] | None = None,
    materials: Iterable[Any] | None = None,
) -> pd.DataFrame:
    """Return a copied summary filtered by any selected group values."""

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    selected = frame.copy(deep=True)
    mask = _isin(selected, "level", _values(levels))
    mask &= _isin(selected, "category", _values(categories))
    mask &= _isin(selected, "material", _values(materials))
    return selected.loc[mask].copy(deep=True)


def filter_elements(
    frame: pd.DataFrame,
    *,
    query: str = "",
    category: Any = "全部",
    level: Any = "全部",
    material: Any = "全部",
) -> pd.DataFrame:
    """Filter element rows by free-text query and optional group values."""

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    selected = frame.copy(deep=True)
    mask = _isin(selected, "category", _values((category,)))
    mask &= _isin(selected, "level", _values((level,)))
    mask &= _isin(selected, "material", _values((material,)))
    text = str(query or "").strip()
    if text:
        searchable = [
            column
            for column in (
                "element_id",
                "guid",
                "element_name",
                "type_name",
                "ifc_class",
                "material",
            )
            if column in selected.columns
        ]
        if not searchable:
            return selected.iloc[0:0].copy(deep=True)
        text_mask = pd.Series(False, index=selected.index)
        for column in searchable:
            text_mask |= selected[column].fillna("").astype(str).str.contains(
                text, case=False, regex=False, na=False
            )
        mask &= text_mask
    return selected.loc[mask].copy(deep=True)


def filter_issues(
    frame: pd.DataFrame,
    *,
    severities: Iterable[Any] | None = None,
    rules: Iterable[Any] | None = None,
) -> pd.DataFrame:
    """Filter serialized quality issues without changing their values."""

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    selected = frame.copy(deep=True)
    mask = _isin(selected, "severity", _values(severities))
    mask &= _isin(selected, "rule_id", _values(rules))
    return selected.loc[mask].copy(deep=True)


def filter_validation(
    frame: pd.DataFrame,
    *,
    categories: Iterable[Any] | None = None,
    minimum_error: float = 0,
) -> pd.DataFrame:
    """Filter validation details by category and absolute-error threshold."""

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    selected = frame.copy(deep=True)
    mask = _isin(selected, "category", _values(categories))
    if "absolute_error" in selected.columns:
        values = pd.to_numeric(selected["absolute_error"], errors="coerce")
        try:
            threshold = max(0.0, float(minimum_error))
        except (TypeError, ValueError, OverflowError):
            threshold = 0.0
        mask &= values.ge(threshold) | values.isna()
    return selected.loc[mask].copy(deep=True)


# Descriptive aliases make the helpers easy to discover from focused tests.
filter_quantity_summary = filter_summary
filter_element_rows = filter_elements
filter_quality_issues = filter_issues
filter_error_details = filter_validation


__all__ = [
    "filter_elements",
    "filter_element_rows",
    "filter_error_details",
    "filter_issues",
    "filter_quality_issues",
    "filter_quantity_summary",
    "filter_summary",
    "filter_validation",
]
