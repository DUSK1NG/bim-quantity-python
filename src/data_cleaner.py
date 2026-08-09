"""Configuration-driven normalization and row-level quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_loader import ProjectConfig
from src.quality_report import QualityIssue, QualityReport
from src.schema import STANDARD_COLUMNS, UNITS


class DataCleaningError(ValueError):
    """A value cannot be safely normalized without losing traceability."""


@dataclass(frozen=True)
class CleaningResult:
    frame: pd.DataFrame
    report: QualityReport


_NUMERIC_COLUMNS = ("length_m", "area_m2", "volume_m3", "quantity", "unit_price", "total_cost")
_NOT_APPLICABLE = ("missing_section_size", "outlier_dimension")
_SEVERITY_RANK = {"Info": 1, "Warning": 2, "Error": 3}


def _basename(value: Any) -> str:
    return str(value).replace("\\", "/").rsplit("/", 1)[-1]


def _strip_strings(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy(deep=True)
    for column in result.columns:
        if result[column].dtype == "object" or pd.api.types.is_string_dtype(result[column]):
            result[column] = result[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            result[column] = result[column].replace("", pd.NA)
    return result


def _aliases(mapping: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, names in mapping.items():
        if isinstance(names, list):
            for name in names:
                lookup[str(name).strip().casefold()] = canonical
    return lookup


def _canonicalize_columns(frame: pd.DataFrame, config: ProjectConfig) -> pd.DataFrame:
    result = frame.copy(deep=True)
    aliases = _aliases(config.field_mapping["aliases"])
    for column in list(result.columns):
        canonical = aliases.get(str(column).strip().casefold(), column)
        if canonical != column:
            if canonical not in result.columns:
                result[canonical] = result[column]
            result = result.drop(columns=[column])
    return result


def _map_value(value: Any, mapping: dict[str, Any]) -> Any:
    if pd.isna(value):
        return value
    text = str(value).strip()
    for canonical, names in mapping.get("aliases", {}).items():
        if text.casefold() == str(canonical).casefold() or any(
            text.casefold() == str(name).casefold() for name in names
        ):
            return canonical
    return text


def _severity_map(config: ProjectConfig) -> dict[str, str]:
    return {
        str(rule["id"]): str(rule["severity"])
        for rule in config.quality_rules["rules"]
    }


def clean_elements(frame: pd.DataFrame, config: ProjectConfig) -> CleaningResult:
    """Normalize a standard elements frame and produce quality findings."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    result = _canonicalize_columns(frame, config)
    if "raw_unit" not in result.columns and "unit" in result.columns:
        result["raw_unit"] = result["unit"]
    raw_unit_values = result["raw_unit"].copy() if "raw_unit" in result.columns else None
    result = _strip_strings(result)
    if raw_unit_values is not None:
        result["raw_unit"] = raw_unit_values

    if "raw_row_number" not in result.columns:
        result["raw_row_number"] = range(1, len(result) + 1)
    if "source_file" not in result.columns:
        result["source_file"] = "unknown.csv"
    result["source_file"] = result["source_file"].map(_basename)
    if "source" not in result.columns:
        result["source"] = "CSV"

    for column in _NUMERIC_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
        original = result[column].copy()
        converted = pd.to_numeric(original, errors="coerce")
        invalid = original.notna() & converted.isna()
        if invalid.any():
            row_index = invalid[invalid].index[0]
            row_number = result.loc[row_index, "raw_row_number"]
            source_file = result.loc[row_index, "source_file"]
            raise DataCleaningError(
                f"字段 {column} 在 {source_file} 的 raw_row_number {row_number} 无法转换为数值；"
                "请修正原始 CSV 后重试。"
            )
        result[column] = converted

    category_mapping = config.category_mapping
    result["category"] = result["category"].map(
        lambda value: _map_value(value, category_mapping)
    )
    result["level"] = result["level"].map(
        lambda value: _map_value(value, config.level_mapping)
    )
    result["material"] = result["material"].map(
        lambda value: _map_value(value, config.material_mapping)
    )

    severity = _severity_map(config)
    issues: list[QualityIssue] = []

    def add(mask: pd.Series, rule_id: str, field: str, message: str) -> None:
        level = severity[rule_id]
        for index in result.index[mask.fillna(False)]:
            issues.append(
                QualityIssue(
                    int(result.loc[index, "raw_row_number"]),
                    rule_id,
                    level,
                    field,
                    message,
                )
            )

    add(result["element_name"].isna(), "missing_element_name", "element_name", "缺失构件名称")
    add(result["type_name"].isna(), "missing_type_name", "type_name", "缺失类型名称")
    add(result["material"].isna(), "missing_material", "material", "缺失材料")
    add(result["level"].isna(), "missing_level", "level", "缺失楼层")
    add(result["guid"].isna(), "missing_guid", "guid", "缺失 GUID")

    for column, rule_id, field, message in (
        ("element_id", "duplicate_element_id", "element_id", "重复构件 ID"),
        ("guid", "duplicate_guid", "guid", "重复 GUID"),
    ):
        duplicated = result[column].notna() & result[column].duplicated(keep=False)
        add(duplicated, rule_id, field, message)

    add(result["quantity"].eq(0), "zero_quantity", "quantity", "工程量为零")
    add(result["quantity"].lt(0), "negative_quantity", "quantity", "工程量为负")

    valid_units = result["unit"].isin(UNITS)
    add(result["unit"].notna() & ~valid_units, "unknown_unit", "unit", "未知单位")

    patterns = config.naming_rules["allowed_patterns"]
    invalid_name = pd.Series(False, index=result.index)
    for index, row in result.iterrows():
        name = row.get("element_name")
        if pd.isna(name):
            continue
        pattern = patterns.get(row.get("ifc_class"))
        if pattern is not None and not __import__("re").fullmatch(pattern, str(name)):
            invalid_name.loc[index] = True
    add(invalid_name, "invalid_name", "element_name", "名称不符合 IFC 类别规则")

    prices = config.unit_prices
    price_keys = set(zip(prices["category"], prices["material"], prices["unit"]))
    matched_prices: list[float | None] = []
    unmatched = pd.Series(False, index=result.index)
    for index, row in result.iterrows():
        key = (row.get("category"), row.get("material"), row.get("unit"))
        match = prices[
            (prices["category"] == key[0])
            & (prices["material"] == key[1])
            & (prices["unit"] == key[2])
        ]
        if not match.empty:
            matched_prices.append(float(match.iloc[0]["unit_price"]))
        else:
            matched_prices.append(None)
            original_price = frame.loc[index, "unit_price"] if "unit_price" in frame.columns else pd.NA
            if (
                key[0] is not None
                and key[1] is not None
                and key[2] in UNITS
                and (
                    key in price_keys
                    or pd.notna(original_price)
                    or key[0] in config.category_mapping["canonical_categories"]
                    and pd.notna(key[1])
                )
            ):
                unmatched.loc[index] = True
    add(unmatched, "unmatched_unit_price", "unit_price", "未匹配教学单价")
    result["unit_price"] = matched_prices
    result["total_cost"] = result["quantity"] * result["unit_price"]

    severity_by_row: dict[int, str] = {}
    for issue in issues:
        current = severity_by_row.get(issue.raw_row_number)
        if current is None or _SEVERITY_RANK[issue.severity] > _SEVERITY_RANK[current]:
            severity_by_row[issue.raw_row_number] = issue.severity
    result["quality_status"] = [
        severity_by_row.get(int(row_number), "Pass")
        for row_number in result["raw_row_number"]
    ]

    counts_by_rule: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for issue in issues:
        counts_by_rule[issue.rule_id] = counts_by_rule.get(issue.rule_id, 0) + 1
        counts_by_severity[issue.severity] = counts_by_severity.get(issue.severity, 0) + 1
    issue_rows = len({issue.raw_row_number for issue in issues})
    field_order = tuple(config.field_mapping["field_order"])
    for column in field_order:
        if column not in result.columns:
            result[column] = pd.NA
    result = result.loc[:, list(field_order)]
    issues = sorted(issues, key=lambda issue: (issue.raw_row_number, issue.rule_id, issue.field))
    return CleaningResult(
        frame=result,
        report=QualityReport(
            total_rows=len(result),
            issue_rows=issue_rows,
            clean_rows=len(result) - issue_rows,
            counts_by_rule=counts_by_rule,
            counts_by_severity=counts_by_severity,
            not_applicable_rules=_NOT_APPLICABLE,
            issues=tuple(issues),
        ),
    )


__all__ = ["CleaningResult", "DataCleaningError", "clean_elements"]
