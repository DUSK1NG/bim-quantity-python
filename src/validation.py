"""Manual quantity review and deterministic error summaries.

The validator compares a calculated standard-field DataFrame with a small
manual review table.  It deliberately keeps the calculated quantity as the
source of the automatic value, uses explicit trace keys, and never mutates
either input frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


class ValidationError(ValueError):
    """A manual review row cannot be associated or safely converted."""


@dataclass(frozen=True)
class ValidationResult:
    """Immutable container for row details, category summaries, and messages."""

    details: pd.DataFrame
    summary_by_category: pd.DataFrame
    messages: tuple[str, ...] = ()


_MATCH_KEYS: tuple[str, ...] = ("guid", "element_id", "raw_row_number")
_DETAIL_COLUMNS: tuple[str, ...] = (
    "match_key_type",
    "match_key",
    "element_id",
    "guid",
    "raw_row_number",
    "source_file",
    "ifc_class",
    "category",
    "level",
    "auto_quantity",
    "manual_quantity",
    "absolute_error",
    "relative_error_pct",
    "manual_row_number",
    "message",
)
_SUMMARY_COLUMNS: tuple[str, ...] = (
    "category",
    "count",
    "mean_absolute_error",
    "max_absolute_error",
    "mean_relative_error_pct",
    "max_relative_error_pct",
)


def _is_missing(value: Any) -> bool:
    """Return whether a scalar has pandas-style missing semantics."""

    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    try:
        return bool(missing)
    except (TypeError, ValueError):
        # Array-like values are outside this row-level contract.
        return False


def _row_number(row: pd.Series, position: int) -> int | str:
    """Use the trace row number, falling back to a one-based table position."""

    value = row.get("raw_row_number", pd.NA)
    if not _is_missing(value):
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            number = math.nan
        if math.isfinite(number) and number.is_integer():
            return int(number)
    return position + 1


def _canonical_key(value: Any, key_type: str) -> str | int | None:
    """Normalize one association key without changing its meaning."""

    if _is_missing(value):
        return None
    if key_type == "raw_row_number":
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(number) or not number.is_integer():
            return None
        return int(number)
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _selected_key(row: pd.Series) -> tuple[str | None, str | int | None]:
    """Select a row's first non-empty key in the documented priority order."""

    for key_type in _MATCH_KEYS:
        if key_type not in row.index:
            continue
        key = _canonical_key(row.get(key_type), key_type)
        if key is not None:
            return key_type, key
    return None, None


def _coerce_quantity(
    value: Any,
    field: str,
    row_number: int | str,
    *,
    allow_missing: bool,
    source_name: str = "人工复核表",
) -> float | None:
    """Convert a quantity and report its original trace row on failure."""

    if _is_missing(value):
        if allow_missing:
            return None
        raise ValidationError(
            f"字段 {field} 在第 {row_number} 行无法转换为数值；请修正{source_name}。"
        )
    if isinstance(value, bool):
        raise ValidationError(
            f"字段 {field} 在第 {row_number} 行无法转换为数值；请修正{source_name}。"
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(
            f"字段 {field} 在第 {row_number} 行无法转换为数值；请修正{source_name}。"
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise ValidationError(
            f"字段 {field} 在第 {row_number} 行不是有限非负数；请修正{source_name}。"
        )
    return number


def _scalar(value: Any) -> Any:
    """Convert pandas missing scalars to ``None`` for stable result frames."""

    return None if _is_missing(value) else value


def _mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    if not values.notna().any():
        return math.nan
    return float(values.mean(skipna=True))


def _maximum(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    if not values.notna().any():
        return math.nan
    return float(values.max(skipna=True))


def _empty_result() -> ValidationResult:
    """Return the typed empty result used for an empty manual table."""

    return ValidationResult(
        details=pd.DataFrame(columns=_DETAIL_COLUMNS),
        summary_by_category=pd.DataFrame(columns=_SUMMARY_COLUMNS),
        messages=(),
    )


def validate_manual_results(
    calculated: pd.DataFrame,
    manual: pd.DataFrame,
) -> ValidationResult:
    """Associate manual quantities and calculate strict comparison errors.

    A manual row chooses ``guid``, then non-empty ``element_id``, then
    ``raw_row_number``.  Duplicate manual keys and keys absent from the
    calculated frame are rejected before any result rows are emitted.
    ``relative_error_pct`` uses the manual quantity as its denominator and is
    intentionally missing for a zero manual value.
    """

    if not isinstance(calculated, pd.DataFrame):
        raise TypeError("calculated 必须是 pandas DataFrame")
    if not isinstance(manual, pd.DataFrame):
        raise TypeError("manual 必须是 pandas DataFrame")
    if "quantity" not in calculated.columns:
        raise ValidationError("计算表缺少标准字段 quantity。")
    if "manual_quantity" not in manual.columns:
        raise ValidationError("人工复核表缺少字段 manual_quantity。")
    if not any(key in calculated.columns for key in _MATCH_KEYS):
        raise ValidationError("计算表缺少匹配键字段（guid、element_id 或 raw_row_number）。")
    if not any(key in manual.columns for key in _MATCH_KEYS):
        raise ValidationError("人工复核表缺少匹配键字段（guid、element_id 或 raw_row_number）。")
    if manual.empty:
        return _empty_result()

    # Build all calculated lookup values, but only reject ambiguity when a
    # selected manual key actually asks for that value.  The sample CSV keeps
    # duplicate GUIDs as a deliberate quality exception unrelated to most
    # manual rows.
    calculated_lookup: dict[str, dict[str | int, list[int]]] = {
        key_type: {} for key_type in _MATCH_KEYS
    }
    for position, (_, row) in enumerate(calculated.iterrows()):
        for key_type in _MATCH_KEYS:
            if key_type not in calculated.columns:
                continue
            key = _canonical_key(row.get(key_type), key_type)
            if key is not None:
                calculated_lookup[key_type].setdefault(key, []).append(position)

    selected: list[tuple[str, str | int, int | str]] = []
    seen_manual: dict[tuple[str, str | int], list[int | str]] = {}
    for position, (_, row) in enumerate(manual.iterrows()):
        manual_row_number = _row_number(row, position)
        key_type, key = _selected_key(row)
        if key_type is None or key is None:
            raise ValidationError(
                f"人工复核表第 {manual_row_number} 行缺少匹配键（guid、element_id 或 raw_row_number）。"
            )
        marker = (key_type, key)
        seen_manual.setdefault(marker, []).append(manual_row_number)
        if len(seen_manual[marker]) > 1:
            rows = ", ".join(str(value) for value in seen_manual[marker])
            raise ValidationError(
                f"重复人工键 {key_type}={key!r}，涉及人工表行号：{rows}。"
            )
        selected.append((key_type, key, manual_row_number))

    detail_rows: list[dict[str, Any]] = []
    messages: list[str] = []

    for manual_position, (_, manual_row) in enumerate(manual.iterrows()):
        key_type, key, manual_row_number = selected[manual_position]
        candidates = calculated_lookup[key_type].get(key, [])
        if not candidates:
            raise ValidationError(
                f"人工复核表第 {manual_row_number} 行的 {key_type}={key!r} 无法匹配计算表。"
            )
        if len(candidates) > 1:
            calculated_rows = [
                str(_row_number(calculated.iloc[position], position))
                for position in candidates
            ]
            raise ValidationError(
                f"计算表 {key_type}={key!r} 对应多行，raw_row_number 为 {', '.join(calculated_rows)}，"
                "无法唯一关联。"
            )

        calculated_position = candidates[0]
        calculated_row = calculated.iloc[calculated_position]
        calculated_row_number = _row_number(calculated_row, calculated_position)
        auto_quantity = _coerce_quantity(
            calculated_row.get("quantity"),
            "quantity",
            calculated_row_number,
            allow_missing=True,
            source_name="计算表",
        )
        manual_quantity = _coerce_quantity(
            manual_row.get("manual_quantity"),
            "manual_quantity",
            manual_row_number,
            allow_missing=False,
        )

        message = ""
        if auto_quantity is None:
            absolute_error = math.nan
            relative_error_pct = math.nan
            message = f"计算表第 {calculated_row_number} 行自动工程量为空，无法计算误差。"
            messages.append(message)
            if manual_quantity == 0:
                zero_message = (
                    f"人工表第 {manual_row_number} 行人工值为零，relative_error_pct 留空；"
                    "自动工程量保持不变。"
                )
                message = f"{message}{zero_message}"
                messages.append(zero_message)
        else:
            absolute_error = abs(auto_quantity - manual_quantity)
            if manual_quantity == 0:
                relative_error_pct = math.nan
                message = (
                    f"人工表第 {manual_row_number} 行人工值为零，relative_error_pct 留空；"
                    "自动工程量保持不变。"
                )
                messages.append(message)
            else:
                relative_error_pct = absolute_error / manual_quantity * 100.0

        detail_rows.append(
            {
                "match_key_type": key_type,
                "match_key": key,
                "element_id": _scalar(calculated_row.get("element_id")),
                "guid": _scalar(calculated_row.get("guid")),
                "raw_row_number": _scalar(calculated_row.get("raw_row_number")),
                "source_file": _scalar(calculated_row.get("source_file")),
                "ifc_class": _scalar(calculated_row.get("ifc_class")),
                "category": _scalar(calculated_row.get("category")),
                "level": _scalar(calculated_row.get("level")),
                "auto_quantity": auto_quantity,
                "manual_quantity": manual_quantity,
                "absolute_error": absolute_error,
                "relative_error_pct": relative_error_pct,
                "manual_row_number": manual_row_number,
                "message": message,
            }
        )

    details = pd.DataFrame(detail_rows, columns=_DETAIL_COLUMNS)
    summary_rows: list[dict[str, Any]] = []
    categories = details["category"].map(
        lambda value: "未分类" if _is_missing(value) else value
    )
    details_for_summary = details.assign(_summary_category=categories)
    for category, group in details_for_summary.groupby(
        "_summary_category", dropna=False, sort=False
    ):
        summary_rows.append(
            {
                "category": category,
                "count": int(len(group)),
                "mean_absolute_error": _mean(group["absolute_error"]),
                "max_absolute_error": _maximum(group["absolute_error"]),
                "mean_relative_error_pct": _mean(group["relative_error_pct"]),
                "max_relative_error_pct": _maximum(group["relative_error_pct"]),
            }
        )
    summary = pd.DataFrame(summary_rows, columns=_SUMMARY_COLUMNS)
    if not summary.empty:
        summary = (
            summary.assign(_sort_category=summary["category"].astype(str))
            .sort_values("_sort_category", kind="stable")
            .drop(columns=["_sort_category"])
            .reset_index(drop=True)
        )

    return ValidationResult(
        details=details,
        summary_by_category=summary,
        messages=tuple(messages),
    )


__all__ = ["ValidationError", "ValidationResult", "validate_manual_results"]
