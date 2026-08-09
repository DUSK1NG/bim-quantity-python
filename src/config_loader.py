"""Load and validate the explicit Phase 2 configuration contract.

The project intentionally keeps configuration small and specialised: six
versioned JSON files describe field/category/level/material/naming/quality
rules, while one CSV contains teaching unit prices.  This module is the only
place that reads those files; later modules receive the validated
``ProjectConfig`` object instead of maintaining hidden mappings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from src.schema import IFC_CLASSES, LEVELS, STANDARD_COLUMNS


CONFIG_VERSION = "2.0"
JSON_FILES = (
    "field_mapping.json",
    "category_mapping.json",
    "level_mapping.json",
    "material_mapping.json",
    "naming_rules.json",
    "quality_rules.json",
)

ALLOWED_KEYS: dict[str, set[str]] = {
    "field_mapping.json": {"config_version", "aliases", "field_order"},
    "category_mapping.json": {
        "config_version",
        "canonical_categories",
        "ifc_class_to_category",
        "aliases",
    },
    "level_mapping.json": {"config_version", "canonical_levels", "aliases"},
    "material_mapping.json": {
        "config_version",
        "canonical_materials",
        "aliases",
    },
    "naming_rules.json": {
        "config_version",
        "allowed_patterns",
        "invalid_name_examples",
    },
    "quality_rules.json": {"config_version", "rules"},
}

TRACE_COLUMNS: tuple[str, ...] = (
    "raw_unit",
    "raw_row_number",
    "source_file",
    "exception_tags",
)
EXPECTED_CATEGORIES: tuple[str, ...] = (
    "Beam",
    "Column",
    "Slab",
    "Wall",
    "Door",
    "Window",
)
EXPECTED_MATERIALS: tuple[str, ...] = ("混凝土", "钢材", "木材", "玻璃", "铝合金")
QUALITY_RULE_IDS: tuple[str, ...] = (
    "missing_element_name",
    "missing_type_name",
    "missing_material",
    "missing_level",
    "missing_guid",
    "duplicate_element_id",
    "zero_quantity",
    "negative_quantity",
    "unknown_unit",
    "invalid_name",
    "missing_section_size",
    "outlier_dimension",
    "duplicate_guid",
    "unmatched_unit_price",
)
QUALITY_SEVERITIES: frozenset[str] = frozenset({"Info", "Warning", "Error"})


class ConfigError(ValueError):
    """A beginner-readable configuration error with a repair suggestion."""


@dataclass(frozen=True)
class ProjectConfig:
    """Validated, read-only top-level project configuration.

    Mapping fields use ``MappingProxyType`` so callers cannot replace their
    top-level entries accidentally.  The price table is copied on load to
    avoid retaining a mutable object owned by the CSV reader.
    """

    config_version: str
    field_mapping: Mapping[str, Any]
    category_mapping: Mapping[str, Any]
    level_mapping: Mapping[str, Any]
    material_mapping: Mapping[str, Any]
    naming_rules: Mapping[str, Any]
    quality_rules: Mapping[str, Any]
    unit_prices: pd.DataFrame


def _load_json(path: Path) -> dict[str, Any]:
    """Read one versioned JSON config and validate its top-level contract."""

    if not path.is_file():
        raise ConfigError(f"缺少 {path.name}；请在 configs/ 下创建该文件后重试。")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(
            f"无法读取 {path.name}：{exc}；请保存为 UTF-8 JSON 后重试。"
        ) from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{path.name} 顶层必须是 JSON 对象；请检查大括号。")

    allowed = ALLOWED_KEYS[path.name]
    unknown = sorted(set(payload) - allowed)
    if unknown:
        names = "、".join(unknown)
        raise ConfigError(
            f"{path.name} 含未知顶层键 {names}；请删除未列入契约的键。"
        )
    missing = sorted(allowed - set(payload))
    if missing:
        names = "、".join(missing)
        raise ConfigError(
            f"{path.name} 缺少顶层键 {names}；请补齐该配置文件的固定结构。"
        )
    if payload["config_version"] != CONFIG_VERSION:
        raise ConfigError(
            f"{path.name} 的 config_version 必须为 {CONFIG_VERSION}；"
            "请修正版本后重试。"
        )
    return payload


def _assert_unique_aliases(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    """Ensure aliases are non-empty strings and globally unique.

    Case and surrounding whitespace are ignored for duplicate detection so a
    mapping cannot silently diverge between English and Chinese inputs.
    """

    seen: dict[str, tuple[str, str, str]] = {}
    for filename, payload in payloads.items():
        if "aliases" not in payload:
            continue
        aliases = payload["aliases"]
        if not isinstance(aliases, dict):
            raise ConfigError(
                f"{filename} 的 aliases 必须是对象；请按 canonical 名称分组。"
            )
        for canonical, values in aliases.items():
            if not isinstance(canonical, str) or not canonical.strip():
                raise ConfigError(
                    f"{filename} 的 aliases 键必须是非空字符串；请修正 canonical 名称。"
                )
            if not isinstance(values, list) or not values:
                raise ConfigError(
                    f"{filename} 的 aliases[{canonical!r}] 必须是非空列表；请补充别名。"
                )
            for alias in values:
                if not isinstance(alias, str) or not alias.strip():
                    raise ConfigError(
                        f"{filename} 的别名必须是非空字符串；请删除空值。"
                    )
                normalized = alias.strip().casefold()
                if normalized in seen:
                    old_canonical, old_filename, old_alias = seen[normalized]
                    raise ConfigError(
                        f"{filename} 存在重复别名 {alias!r}（已在 "
                        f"{old_filename}:{old_canonical} 使用 {old_alias!r}）；"
                        "请保留一个归属。"
                    )
                seen[normalized] = (str(canonical), filename, alias)


def _validate_field_order(payload: Mapping[str, Any]) -> None:
    field_order = payload.get("field_order")
    if not isinstance(field_order, list) or not all(
        isinstance(value, str) for value in field_order
    ):
        raise ConfigError(
            "field_mapping.json 的 field_order 必须是字符串列表；"
            "请按标准字段顺序填写。"
        )
    expected = [*STANDARD_COLUMNS, *TRACE_COLUMNS]
    if field_order != expected:
        raise ConfigError(
            "field_mapping.json 的 field_order 必须完全等于 STANDARD_COLUMNS "
            "后接 raw_unit、raw_row_number、source_file、exception_tags；"
            "请修正字段顺序、重复项和字段数量。"
        )


def _validate_alias_keys(
    filename: str, aliases: Any, expected: tuple[str, ...]
) -> None:
    """Ensure a mapping's alias groups cover each canonical name exactly once."""

    if not isinstance(aliases, dict):
        raise ConfigError(f"{filename} 的 aliases 必须是对象；请按 canonical 名称分组。")
    actual = set(aliases)
    expected_set = set(expected)
    if actual != expected_set:
        unknown = "、".join(sorted(actual - expected_set)) or "无"
        missing = "、".join(sorted(expected_set - actual)) or "无"
        raise ConfigError(
            f"{filename} 的 aliases canonical 键必须与规范列表完全一致；"
            f"未知键：{unknown}，缺少键：{missing}。请修正 aliases。"
        )


def _validate_category_mapping(payload: Mapping[str, Any]) -> None:
    canonical = payload["canonical_categories"]
    if canonical != list(EXPECTED_CATEGORIES):
        raise ConfigError(
            "category_mapping.json 的 canonical_categories 必须严格为 "
            "Beam、Column、Slab、Wall、Door、Window；请修正类别列表。"
        )

    mapping = payload["ifc_class_to_category"]
    if not isinstance(mapping, dict) or set(mapping) != set(IFC_CLASSES):
        actual = set(mapping) if isinstance(mapping, dict) else set()
        unknown = "、".join(sorted(actual - set(IFC_CLASSES))) or "无"
        missing = "、".join(sorted(set(IFC_CLASSES) - actual)) or "无"
        raise ConfigError(
            "category_mapping.json 的 IFC ifc_class_to_category 键必须与 schema.IFC_CLASSES "
            f"完全一致；未知键：{unknown}，缺少键：{missing}。请修正 IFC 映射。"
        )
    expected_mapping = dict(zip(IFC_CLASSES, EXPECTED_CATEGORIES))
    if mapping != expected_mapping:
        raise ConfigError(
            "category_mapping.json 的 IFC 映射必须按 IFC 类别一对一对应 "
            "Beam/Column/Slab/Wall/Door/Window；请修正 ifc_class_to_category。"
        )
    _validate_alias_keys(
        "category_mapping.json", payload["aliases"], EXPECTED_CATEGORIES
    )


def _validate_level_mapping(payload: Mapping[str, Any]) -> None:
    if payload["canonical_levels"] != list(LEVELS):
        raise ConfigError(
            "level_mapping.json 的 canonical_levels 必须严格为 一层、二层、三层；"
            "请修正楼层列表。"
        )
    _validate_alias_keys("level_mapping.json", payload["aliases"], LEVELS)


def _validate_material_mapping(payload: Mapping[str, Any]) -> None:
    if payload["canonical_materials"] != list(EXPECTED_MATERIALS):
        raise ConfigError(
            "material_mapping.json 的 canonical_materials 必须严格为 "
            "混凝土、钢材、木材、玻璃、铝合金；请修正材料列表。"
        )
    _validate_alias_keys(
        "material_mapping.json", payload["aliases"], EXPECTED_MATERIALS
    )


def _validate_naming_rules(payload: Mapping[str, Any]) -> None:
    patterns = payload["allowed_patterns"]
    if not isinstance(patterns, dict) or set(patterns) != set(IFC_CLASSES):
        raise ConfigError(
            "naming_rules.json 的 allowed_patterns 必须覆盖 IFC_CLASSES 且不能多或少；"
            "请为每个 IFC 类别配置一个正则。"
        )
    for ifc_class in IFC_CLASSES:
        pattern = patterns[ifc_class]
        if not isinstance(pattern, str) or not pattern.strip():
            raise ConfigError(
                f"naming_rules.json 的 {ifc_class} 正则必须是非空字符串；请补充模式。"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(
                f"naming_rules.json 的 {ifc_class} 正则无法编译；请修正正则表达式。"
            ) from exc

    examples = payload["invalid_name_examples"]
    if not isinstance(examples, list) or not examples or any(
        not isinstance(example, str) or not example.strip() for example in examples
    ):
        raise ConfigError(
            "naming_rules.json 的 invalid_name_examples 必须是非空字符串列表；"
            "请删除空值。"
        )
    normalized = [example.strip() for example in examples]
    if len(set(normalized)) != len(normalized):
        raise ConfigError(
            "naming_rules.json 的 invalid_name_examples 不能重复；请保留唯一示例。"
        )


def _validate_quality_rules(payload: Mapping[str, Any]) -> None:
    rules = payload["rules"]
    if not isinstance(rules, list) or len(rules) != len(QUALITY_RULE_IDS):
        raise ConfigError(
            "quality_rules.json 的 rules 必须包含恰好 14 条规则；请补齐或删除多余规则。"
        )

    expected_keys = {"id", "severity"}
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict) or set(rule) != expected_keys:
            raise ConfigError(
                f"quality_rules.json 第 {index} 条规则必须只包含 id、severity 两个键；"
                "请修正规则结构。"
            )

    ids = [rule["id"] for rule in rules]
    if any(not isinstance(rule_id, str) or not rule_id.strip() for rule_id in ids):
        raise ConfigError(
            "quality_rules.json 的每个规则 id 必须是非空字符串；请修正规则 ID。"
        )
    if len(set(ids)) != len(ids):
        raise ConfigError(
            "quality_rules.json 含重复规则 id；请为每条规则保留唯一 ID。"
        )
    unknown = sorted(set(ids) - set(QUALITY_RULE_IDS))
    missing = sorted(set(QUALITY_RULE_IDS) - set(ids))
    if unknown or missing:
        unknown_text = "、".join(unknown) or "无"
        missing_text = "、".join(missing) or "无"
        raise ConfigError(
            "quality_rules.json 含未知或缺失规则 id；"
            f"未知：{unknown_text}，缺少：{missing_text}。请使用计划中的 14 个 ID。"
        )

    for index, rule in enumerate(rules, start=1):
        severity = rule["severity"]
        if not isinstance(severity, str) or severity not in QUALITY_SEVERITIES:
            allowed = "、".join(sorted(QUALITY_SEVERITIES))
            raise ConfigError(
                f"quality_rules.json 第 {index} 条规则的 severity={severity!r} 无效；"
                f"只能使用 {allowed}。请修正严重程度。"
            )


def _load_unit_prices(config_dir: Path) -> pd.DataFrame:
    path = config_dir / "sample_unit_prices.csv"
    if not path.is_file():
        raise ConfigError(
            "缺少 sample_unit_prices.csv；请添加教学单价表后重试。"
        )
    try:
        prices = pd.read_csv(path)
    except (
        OSError,
        UnicodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        raise ConfigError(
            f"无法读取 sample_unit_prices.csv：{exc}；请保存为 UTF-8 CSV。"
        ) from exc

    required = ["category", "material", "unit", "unit_price"]
    missing = [column for column in required if column not in prices.columns]
    if missing:
        raise ConfigError(
            "sample_unit_prices.csv 缺少列 "
            f"{', '.join(missing)}；请使用固定表头 category,material,unit,unit_price。"
        )
    if list(prices.columns) != required:
        raise ConfigError(
            "sample_unit_prices.csv 列顺序必须为 "
            "category,material,unit,unit_price；请调整表头。"
        )

    converted = pd.to_numeric(prices["unit_price"], errors="coerce")
    if converted.isna().any() or (converted <= 0).any():
        raise ConfigError(
            "sample_unit_prices.csv 的 unit_price 必须是正数；"
            "请删除空值、文字和零/负数。"
        )
    prices = prices.copy()
    prices["unit_price"] = converted.astype(float)

    key_frame = prices[["category", "material", "unit"]].astype(str)
    if key_frame.duplicated().any():
        raise ConfigError(
            "sample_unit_prices.csv 含重复 category/material/unit；"
            "请合并重复价格行。"
        )
    return prices


def load_project_config(config_dir: Path) -> ProjectConfig:
    """Read and strictly validate all seven Phase 2 config files.

    ``config_dir`` is intentionally a concrete ``Path`` boundary.  Any
    malformed config raises ``ConfigError`` before downstream business code
    starts, so later tasks can consume one deterministic object.
    """

    directory = Path(config_dir)
    payloads = {
        filename: _load_json(directory / filename) for filename in JSON_FILES
    }
    _validate_field_order(payloads["field_mapping.json"])
    _validate_category_mapping(payloads["category_mapping.json"])
    _validate_level_mapping(payloads["level_mapping.json"])
    _validate_material_mapping(payloads["material_mapping.json"])
    _validate_naming_rules(payloads["naming_rules.json"])
    _validate_quality_rules(payloads["quality_rules.json"])
    _assert_unique_aliases(payloads)
    prices = _load_unit_prices(directory)

    return ProjectConfig(
        config_version=CONFIG_VERSION,
        field_mapping=MappingProxyType(payloads["field_mapping.json"]),
        category_mapping=MappingProxyType(payloads["category_mapping.json"]),
        level_mapping=MappingProxyType(payloads["level_mapping.json"]),
        material_mapping=MappingProxyType(payloads["material_mapping.json"]),
        naming_rules=MappingProxyType(payloads["naming_rules.json"]),
        quality_rules=MappingProxyType(payloads["quality_rules.json"]),
        unit_prices=prices.copy(deep=True),
    )
