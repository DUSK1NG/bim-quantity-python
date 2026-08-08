"""Deterministic fourteen-rule quality checks for a standard element table.

The checker consumes the cleaned/calculated DataFrame contract.  It does not
normalise aliases, change quantities, or drop rows; those concerns belong to
the preceding modules.  Findings are represented by the shared immutable
``QualityIssue``/``QualityReport`` dataclasses.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

import pandas as pd

from src.config_loader import ProjectConfig
from src.quality_report import (
    ALLOWED_SEVERITIES,
    NOT_APPLICABLE_RULES,
    QualityIssue,
    QualityReport,
)
from src.schema import UNITS


# Explanations and repair suggestions deliberately live beside the checker,
# not in field/category mapping configuration.  The rule IDs and severities
# themselves always come from ProjectConfig.
_MESSAGES: dict[str, tuple[str, str]] = {
    "missing_element_name": ("缺失构件名称", "建议补充构件名称"),
    "missing_type_name": ("缺失类型名称", "建议补充类型名称"),
    "missing_material": ("缺失材料", "建议补充标准材料"),
    "missing_level": ("缺失楼层", "建议补充标准楼层"),
    "missing_guid": ("缺失 GUID", "建议补充唯一 GUID"),
    "duplicate_element_id": ("重复构件 ID", "建议为每个构件分配唯一 ID"),
    "zero_quantity": ("工程量为零", "建议核对尺寸和工程量来源"),
    "negative_quantity": ("工程量为负", "建议修正工程量为非负数"),
    "unknown_unit": ("未知单位", "建议改用标准单位"),
    "invalid_name": ("名称不符合 IFC 类别规则", "建议按 IFC 类别修正名称"),
    "missing_section_size": ("缺失截面尺寸", "建议补充截面尺寸配置"),
    "outlier_dimension": ("尺寸明显异常", "建议复核尺寸和单位"),
    "duplicate_guid": ("重复 GUID", "建议为每个构件分配唯一 GUID"),
    "unmatched_unit_price": ("未匹配教学单价", "建议检查类别、材料和单位的价格配置"),
}


def _is_missing(value: Any) -> bool:
    """Return whether one scalar is empty under the cleaned-field contract."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(missing)
    except (TypeError, ValueError):
        # Non-scalar values are outside the standard row contract.  Treating
        # them as present lets the caller see the resulting rule finding.
        return False


def _row_number(row: pd.Series, position: int) -> int:
    """Read a trace row number, falling back to one-based position."""

    value = row.get("raw_row_number")
    if not _is_missing(value):
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            number = math.nan
        if math.isfinite(number) and number.is_integer():
            return int(number)
    return position + 1


def _trace_value(value: Any, *, source_file: bool = False) -> Any:
    """Return a JSON-safe row trace value, reducing source paths to basenames."""

    if _is_missing(value):
        return None
    if source_file:
        return str(value).replace("\\", "/").rsplit("/", 1)[-1]
    return value


def _nonempty_mask(series: pd.Series) -> pd.Series:
    """Return a bool mask for scalar values which are not blank or missing."""

    return series.map(lambda value: not _is_missing(value))


def _duplicate_mask(series: pd.Series) -> pd.Series:
    """Mark every row in a duplicate non-empty value group."""

    nonempty = _nonempty_mask(series)
    # ``duplicated`` handles the normal scalar values used by the schema and
    # gives the desired keep=False group semantics.  Restricting the input to
    # non-empty values is important: blank IDs/GUIDs are missing, not a shared
    # identifier.
    values = series.where(nonempty)
    return nonempty & values.duplicated(keep=False)


def _finite_number(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _same_value(left: Any, right: Any) -> bool:
    if _is_missing(left) or _is_missing(right):
        return _is_missing(left) and _is_missing(right)
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _fallback_material(value: Any) -> bool:
    """Recognise the explicit material-independent price markers."""

    if _is_missing(value):
        return True
    if not isinstance(value, str):
        return False
    return value.strip().casefold() in {"", "*", "any", "default", "默认", "兜底"}


def _has_configured_price(row: pd.Series, prices: pd.DataFrame) -> bool:
    """Return whether category/material/unit has an exact configured price."""

    category = row.get("category")
    material = row.get("material")
    unit = row.get("unit")
    if _is_missing(category) or _is_missing(material) or _is_missing(unit):
        return False

    for _, price_row in prices.iterrows():
        if (
            _same_value(price_row.get("category"), category)
            and _same_value(price_row.get("material"), material)
            and _same_value(price_row.get("unit"), unit)
        ):
            return True

    # Category/unit fallback is only enabled when the config explicitly marks
    # a material-independent row; ordinary material names are never guessed.
    for _, price_row in prices.iterrows():
        if (
            _same_value(price_row.get("category"), category)
            and _same_value(price_row.get("unit"), unit)
            and _fallback_material(price_row.get("material"))
        ):
            return True
    return False


def _severity_map(config: ProjectConfig) -> tuple[dict[str, str], tuple[str, ...]]:
    """Read rule IDs/severities in their validated config order."""

    specs = config.quality_rules.get("rules", [])
    severity: dict[str, str] = {}
    rule_ids: list[str] = []
    for spec in specs:
        if not isinstance(spec, Mapping):
            continue
        rule_id = str(spec.get("id", ""))
        if not rule_id:
            continue
        rule_ids.append(rule_id)
        configured = str(spec.get("severity", "Warning"))
        severity[rule_id] = configured if configured in ALLOWED_SEVERITIES else "Warning"
    return severity, tuple(rule_ids)


def check_quality(frame: pd.DataFrame, config: ProjectConfig) -> QualityReport:
    """Check all configured row-level quality rules without mutating ``frame``.

    The two dimension rules are deliberately marked not applicable because
    the current project configuration has no section-size thresholds.  The
    returned report retains every input row through ``total_rows`` and uses
    ``raw_row_number`` (or a deterministic one-based fallback) for findings.
    """

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if not isinstance(config, ProjectConfig):
        raise TypeError("config must be a ProjectConfig")

    severity, configured_ids = _severity_map(config)
    # A validated ProjectConfig always contains all 14 IDs.  Keeping the
    # implementation tolerant of a hand-built config makes the checker easier
    # to use in focused tests while preserving config-driven severities.
    issues: list[QualityIssue] = []

    def add(position: int, row: pd.Series, rule_id: str, field: str) -> None:
        level = severity.get(rule_id, "Warning")
        explanation, suggestion = _MESSAGES.get(
            rule_id,
            (f"质量规则 {rule_id} 未通过", "建议检查该字段"),
        )
        issues.append(
            QualityIssue(
                raw_row_number=_row_number(row, position),
                rule_id=rule_id,
                severity=level,
                field=field,
                message=f"{explanation}；{suggestion}",
                source_file=_trace_value(row.get("source_file"), source_file=True),
                guid=_trace_value(row.get("guid")),
                element_name=_trace_value(row.get("element_name")),
                type_name=_trace_value(row.get("type_name")),
                level=_trace_value(row.get("level")),
                suggestion=suggestion,
            )
        )

    # Build per-column series with a missing placeholder for sparse hand-built
    # frames.  Cleaned production frames contain all standard fields, but the
    # checker should still report useful findings instead of raising KeyError.
    columns = {
        name: frame[name] if name in frame.columns else pd.Series(pd.NA, index=frame.index)
        for name in (
            "element_name",
            "type_name",
            "material",
            "level",
            "guid",
            "element_id",
            "quantity",
            "unit",
            "ifc_class",
            "category",
        )
    }

    missing_rules = (
        ("element_name", "missing_element_name"),
        ("type_name", "missing_type_name"),
        ("material", "missing_material"),
        ("level", "missing_level"),
        ("guid", "missing_guid"),
    )
    for field, rule_id in missing_rules:
        if rule_id not in severity:
            continue
        mask = columns[field].map(_is_missing)
        for position, (index, row) in enumerate(frame.iterrows()):
            if bool(mask.loc[index]):
                add(position, row, rule_id, field)

    for field, rule_id in (
        ("element_id", "duplicate_element_id"),
        ("guid", "duplicate_guid"),
    ):
        if rule_id not in severity:
            continue
        mask = _duplicate_mask(columns[field])
        for position, (index, row) in enumerate(frame.iterrows()):
            if bool(mask.loc[index]):
                add(position, row, rule_id, field)

    quantity = columns["quantity"]
    for position, (index, row) in enumerate(frame.iterrows()):
        number = _finite_number(quantity.loc[index])
        if "zero_quantity" in severity and number is not None and number == 0:
            add(position, row, "zero_quantity", "quantity")
        if "negative_quantity" in severity:
            # Preserve the distinction between an invalid/non-numeric value
            # and a genuine negative quantity; non-finite values are handled
            # by the upstream calculation/cleaning stage.
            try:
                raw_number = float(quantity.loc[index])
            except (TypeError, ValueError, OverflowError):
                raw_number = math.nan
            if math.isfinite(raw_number) and raw_number < 0:
                add(position, row, "negative_quantity", "quantity")

    units = columns["unit"]
    if "unknown_unit" in severity:
        for position, (index, row) in enumerate(frame.iterrows()):
            value = units.loc[index]
            if not _is_missing(value) and value not in UNITS:
                add(position, row, "unknown_unit", "unit")

    if "invalid_name" in severity:
        patterns = config.naming_rules.get("allowed_patterns", {})
        for position, (index, row) in enumerate(frame.iterrows()):
            name = columns["element_name"].loc[index]
            if _is_missing(name):
                continue
            pattern = patterns.get(columns["ifc_class"].loc[index])
            if pattern is not None and re.fullmatch(str(pattern), str(name)) is None:
                add(position, row, "invalid_name", "element_name")

    if "unmatched_unit_price" in severity:
        prices = config.unit_prices
        for position, (index, row) in enumerate(frame.iterrows()):
            category = columns["category"].loc[index]
            material = columns["material"].loc[index]
            unit = units.loc[index]
            if (
                _is_missing(category)
                or _is_missing(material)
                or _is_missing(unit)
                or unit not in UNITS
            ):
                continue
            if not _has_configured_price(row, prices):
                add(position, row, "unmatched_unit_price", "unit_price")

    issues.sort(key=lambda issue: (issue.raw_row_number, issue.rule_id, issue.field))

    counts_by_rule: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for issue in issues:
        counts_by_rule[issue.rule_id] = counts_by_rule.get(issue.rule_id, 0) + 1
        counts_by_severity[issue.severity] = counts_by_severity.get(issue.severity, 0) + 1

    issue_rows = len(
        {
            (
                _trace_value(issue.source_file, source_file=True) or "",
                issue.raw_row_number,
            )
            for issue in issues
        }
    )
    return QualityReport(
        total_rows=len(frame),
        issue_rows=issue_rows,
        clean_rows=len(frame) - issue_rows,
        counts_by_rule=counts_by_rule,
        counts_by_severity=counts_by_severity,
        not_applicable_rules=NOT_APPLICABLE_RULES,
        issues=tuple(issues),
    )


__all__ = ["check_quality"]
