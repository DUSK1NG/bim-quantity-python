"""Load and validate the explicit Phase 2 configuration contract.

The project intentionally keeps configuration small and specialised: six
versioned JSON files describe field/category/level/material/naming/quality
rules, while one CSV contains teaching unit prices.  This module is the only
place that reads those files; later modules receive the validated
``ProjectConfig`` object instead of maintaining hidden mappings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from src.schema import STANDARD_COLUMNS


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
    expected = list(STANDARD_COLUMNS)
    if field_order[: len(expected)] != expected:
        raise ConfigError(
            "field_mapping.json 的 field_order 必须以 STANDARD_COLUMNS 原顺序开头；"
            "请修正字段顺序并保留全部标准字段。"
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
    _assert_unique_aliases(payloads)
    _validate_field_order(payloads["field_mapping.json"])
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
