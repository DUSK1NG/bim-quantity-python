"""Optional, deliberately thin IfcOpenShell adapter.

The project keeps IFC support behind this module so importing ``src`` and the
CSV pipeline never imports the optional IfcOpenShell dependency.  The reader
extracts only explicit, well-known attributes and leaves anything uncertain as
``pd.NA`` with a human-readable diagnostic.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import pandas as pd

from src.config_loader import ProjectConfig
from src.schema import IFC_CLASSES, STANDARD_COLUMNS


TRACE_COLUMNS: tuple[str, ...] = (
    "raw_unit",
    "raw_row_number",
    "source_file",
    "exception_tags",
)


class IfcReaderUnavailable(RuntimeError):
    """IfcOpenShell is not installed or cannot be imported."""


class IfcReaderError(RuntimeError):
    """The IFC file or one of its readable model boundaries is invalid."""


@dataclass(frozen=True)
class IfcReadResult:
    """Immutable container returned by :func:`read_ifc`."""

    frame: pd.DataFrame
    diagnostics: tuple[str, ...] = ()


_SUPPORTED: frozenset[str] = frozenset(IFC_CLASSES)
_MISSING = pd.NA

_ID_KEYS: tuple[str, ...] = (
    "ElementId",
    "ElementID",
    "element_id",
    "ElementIdentifier",
    "Identification",
    "Tag",
    "编号",
)
_GUID_KEYS: tuple[str, ...] = ("GlobalId", "global_id", "guid", "GUID")
_NAME_KEYS: tuple[str, ...] = ("Name", "name", "ElementName", "element_name")
_TYPE_KEYS: tuple[str, ...] = (
    "ObjectType",
    "object_type",
    "TypeName",
    "type_name",
    "Type",
)
_LEVEL_KEYS: tuple[str, ...] = (
    "Level",
    "level",
    "Storey",
    "storey",
    "BuildingStorey",
    "building_storey",
)
_MATERIAL_KEYS: tuple[str, ...] = ("Material", "material", "Materials", "materials")
_UNIT_KEYS: tuple[str, ...] = ("Unit", "unit", "UnitName", "raw_unit")

_QUANTITY_KEYS: dict[str, tuple[str, ...]] = {
    "length_m": (
        "length_m",
        "Length",
        "LengthValue",
        "length",
        "GrossLength",
        "NetLength",
    ),
    "area_m2": (
        "area_m2",
        "Area",
        "AreaValue",
        "area",
        "GrossArea",
        "NetArea",
        "GrossSurfaceArea",
        "NetSurfaceArea",
    ),
    "volume_m3": (
        "volume_m3",
        "Volume",
        "VolumeValue",
        "volume",
        "GrossVolume",
        "NetVolume",
    ),
    "quantity": (
        "quantity",
        "Quantity",
        "Count",
        "CountValue",
        "GrossQuantity",
        "NetQuantity",
    ),
}

_BASE_CONTAINER_KEYS: tuple[str, ...] = (
    "BaseQuantities",
    "base_quantities",
    "BaseQuantity",
    "base_quantity",
    "ElementQuantities",
    "element_quantities",
    "IsDefinedBy",
)

_UNIT_ALIASES: dict[str, str] = {
    "m": "m",
    "meter": "m",
    "metre": "m",
    "meters": "m",
    "metres": "m",
    "米": "m",
    "m2": "m²",
    "m^2": "m²",
    "m²": "m²",
    "squaremeter": "m²",
    "squaremetre": "m²",
    "平方米": "m²",
    "m3": "m³",
    "m^3": "m³",
    "m³": "m³",
    "cubicmeter": "m³",
    "cubicmetre": "m³",
    "立方米": "m³",
    "count": "个",
    "counts": "个",
    "each": "个",
    "ea": "个",
    "个": "个",
    "piece": "个",
    "樘": "樘",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, bool) else False


def _finite_nonnegative(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _text(value: Any) -> str | Any:
    """Trim a scalar text value while retaining non-text values for numeric use."""

    if _is_missing(value):
        return _MISSING
    if isinstance(value, str):
        value = value.strip()
        return value if value else _MISSING
    return value


def _key(value: Any) -> str:
    return str(value).strip().casefold()


def _iter_values(value: Any) -> Iterator[Any]:
    if _is_missing(value):
        return
    if isinstance(value, (str, bytes)):
        yield value
        return
    if isinstance(value, Mapping):
        yield value
        return
    try:
        iterator = iter(value)
    except TypeError:
        yield value
        return
    for item in iterator:
        yield item


def _direct_value(obj: Any, names: Iterable[str], info: Mapping[str, Any] | None = None) -> Any:
    """Read one of a finite list of explicit attributes or info keys."""

    for name in names:
        try:
            value = getattr(obj, name)
        except (AttributeError, KeyError, TypeError):
            value = _MISSING
        if callable(value):
            try:
                value = value()
            except TypeError:
                value = _MISSING
            except Exception:
                value = _MISSING
        if not _is_missing(value):
            return value
    if info:
        lowered = {_key(name): value for name, value in info.items()}
        for name in names:
            value = lowered.get(_key(name), _MISSING)
            if not _is_missing(value):
                return value
    return _MISSING


def _safe_info(entity: Any) -> Mapping[str, Any]:
    try:
        getter = getattr(entity, "get_info", None)
        if callable(getter):
            info = getter()
            if isinstance(info, Mapping):
                return info
    except Exception:
        return {}
    return {}


def _entity_class(entity: Any, info: Mapping[str, Any] | None = None) -> str | None:
    try:
        is_a = getattr(entity, "is_a", None)
        if callable(is_a):
            value = is_a()
            if isinstance(value, str) and value:
                return value
            # A few lightweight IFC doubles expose only ``is_a(name)``.
            for supported in IFC_CLASSES:
                try:
                    if is_a(supported):
                        return supported
                except Exception:
                    continue
    except Exception:
        pass
    value = _direct_value(entity, ("ifc_class", "IfcClass", "type"), info)
    if isinstance(value, str) and value:
        return value
    if info:
        value = info.get("type")
        if isinstance(value, str) and value:
            return value
    return None


def _canonical(value: Any, mapping: Mapping[str, Any] | None) -> Any:
    value = _text(value)
    if _is_missing(value) or not mapping:
        return value
    aliases = mapping.get("aliases", {})
    text_value = str(value).casefold()
    for canonical, names in aliases.items():
        if text_value == str(canonical).casefold():
            return canonical
        if isinstance(names, (list, tuple, set, frozenset)) and any(
            text_value == str(name).casefold() for name in names
        ):
            return canonical
    return value


def _material_names(value: Any) -> list[str]:
    """Extract explicit display names from material objects/associations."""

    if _is_missing(value):
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Mapping):
        names: list[str] = []
        for candidate in ("Name", "name", "MaterialName", "material"):
            if candidate in value:
                names.extend(_material_names(value[candidate]))
        for candidate in ("Materials", "materials"):
            if candidate in value:
                names.extend(_material_names(value[candidate]))
        return names
    names = []
    for candidate in ("Name", "name", "MaterialName", "material"):
        try:
            candidate_value = getattr(value, candidate)
        except (AttributeError, TypeError):
            continue
        names.extend(_material_names(candidate_value))
    for candidate in ("Materials", "materials"):
        try:
            candidate_value = getattr(value, candidate)
        except (AttributeError, TypeError):
            continue
        names.extend(_material_names(candidate_value))
    if not names:
        try:
            names.extend(_material_names(value.get_info()))
        except Exception:
            pass
    return names


def _relationship_values(entity: Any, names: Iterable[str]) -> list[Any]:
    result: list[Any] = []
    for name in names:
        try:
            value = getattr(entity, name)
        except (AttributeError, TypeError):
            continue
        if callable(value):
            try:
                value = value()
            except Exception:
                continue
        result.extend(list(_iter_values(value)))
    return result


def _extract_level(entity: Any, info: Mapping[str, Any], config: ProjectConfig) -> Any:
    value = _direct_value(entity, _LEVEL_KEYS, info)
    if not _is_missing(value):
        return _canonical(value, config.level_mapping)
    relations = _relationship_values(
        entity,
        ("ContainedInStructure", "ContainedInSpatialStructure", "SpatialContainer", "Container"),
    )
    for relation in relations:
        structure = _direct_value(relation, ("RelatingStructure", "BuildingStorey", "Storey", "Structure"))
        if _is_missing(structure):
            structure = relation
        value = _direct_value(structure, ("Name", "LongName", "name", "level"))
        if not _is_missing(value):
            return _canonical(value, config.level_mapping)
    return _MISSING


def _extract_type_name(entity: Any, info: Mapping[str, Any]) -> Any:
    value = _direct_value(entity, _TYPE_KEYS, info)
    if not _is_missing(value) and not isinstance(value, (list, tuple, dict)):
        return _text(value)
    for relation in _relationship_values(entity, ("IsTypedBy", "TypedBy", "TypeRelation")):
        type_object = _direct_value(relation, ("RelatingType", "Type", "type"))
        if _is_missing(type_object):
            type_object = relation
        value = _direct_value(type_object, ("Name", "name", "TypeName", "type_name"))
        if not _is_missing(value):
            return _text(value)
    return _MISSING


def _extract_material(entity: Any, info: Mapping[str, Any], config: ProjectConfig) -> tuple[Any, bool]:
    values: list[Any] = []
    direct = _direct_value(entity, _MATERIAL_KEYS, info)
    if not _is_missing(direct):
        values.extend(_material_names(direct))
    for relation in _relationship_values(entity, ("HasAssociations", "AssociatesMaterial", "MaterialAssociations")):
        related = _direct_value(relation, ("RelatingMaterial", "Material", "material"))
        if _is_missing(related):
            related = relation
        values.extend(_material_names(related))
    unique: list[str] = []
    for value in values:
        canonical = _canonical(value, config.material_mapping)
        if _is_missing(canonical):
            continue
        text_value = str(canonical)
        if text_value not in unique:
            unique.append(text_value)
    return ("; ".join(unique) if unique else _MISSING, len(unique) > 1)


def _walk_sources(value: Any, seen: set[int] | None = None) -> Iterator[Any]:
    """Walk only known IFC quantity containers, avoiding a generic parser."""

    if _is_missing(value):
        return
    seen = seen or set()
    marker = id(value)
    if marker in seen:
        return
    seen.add(marker)
    yield value
    if isinstance(value, Mapping):
        for key in _BASE_CONTAINER_KEYS + ("Quantities", "quantities", "HasProperties", "Properties"):
            if key in value:
                yield from _walk_sources(value[key], seen)
        return
    for key in _BASE_CONTAINER_KEYS + ("Quantities", "quantities", "HasProperties", "Properties", "RelatingPropertyDefinition"):
        try:
            nested = getattr(value, key)
        except (AttributeError, TypeError):
            continue
        if callable(nested):
            try:
                nested = nested()
            except Exception:
                continue
        yield from _walk_sources(nested, seen)


def _find_quantity(source: Any, aliases: Iterable[str]) -> Any:
    aliases_ordered = tuple(aliases)
    aliases_set = {_key(alias) for alias in aliases_ordered}
    if isinstance(source, Mapping):
        values = {_key(name): value for name, value in source.items()}
        for alias in aliases_ordered:
            value = values.get(_key(alias), _MISSING)
            if _key(alias) in aliases_set and not _is_missing(value):
                return value
        return _MISSING
    info = _safe_info(source)
    value = _direct_value(source, aliases, info)
    return value


def _normalise_unit(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    normalised = text_value.casefold().replace(" ", "")
    return _UNIT_ALIASES.get(normalised)


def _default_unit(category: Any) -> str | None:
    return {
        "Beam": "m",
        "Column": "m³",
        "Slab": "m³",
        "Wall": "m³",
        "Door": "樘",
        "Window": "樘",
    }.get(category)


def _extract_quantities(
    entity: Any,
    info: Mapping[str, Any],
    category: Any,
    row_number: int,
    diagnostics: list[str],
    tags: list[str],
) -> dict[str, Any]:
    sources: list[Any] = []
    for name in _BASE_CONTAINER_KEYS:
        value = _direct_value(entity, (name,), info)
        if not _is_missing(value):
            sources.extend(_walk_sources(value))
    sources.extend(_walk_sources(entity))

    result: dict[str, Any] = {column: _MISSING for column in _QUANTITY_KEYS}
    found_values: dict[str, Any] = {}
    for column, aliases in _QUANTITY_KEYS.items():
        for source in sources:
            value = _find_quantity(source, aliases)
            if not _is_missing(value):
                found_values[column] = value
                break
        if column in found_values:
            numeric = _finite_nonnegative(found_values[column])
            if numeric is None:
                tags.append(f"bad_{column}")
                diagnostics.append(
                    f"Warning: 实体序号 {row_number} 的 Base Quantity {column} 不是有限非负数；已保留缺失值。"
                )
            else:
                result[column] = numeric

    raw_unit = _direct_value(entity, _UNIT_KEYS, info)
    if _is_missing(raw_unit):
        for source in sources:
            raw_unit = _find_quantity(source, _UNIT_KEYS)
            if not _is_missing(raw_unit):
                break
    result["raw_unit"] = _text(raw_unit)
    unit = _normalise_unit(raw_unit)
    if not _is_missing(raw_unit) and unit is None:
        tags.append("unknown_unit")
        diagnostics.append(
            f"Warning: 实体序号 {row_number} 的 IFC 单位无法识别；数量保留缺失值。"
        )
        result["unit"] = _MISSING
        result["quantity"] = _MISSING
    else:
        if unit is None:
            unit = _default_unit(category)
        result["unit"] = unit if unit is not None else _MISSING
    if not _is_missing(result["quantity"]) and not _is_missing(result["unit"]):
        result["quantity_source"] = "IFC BaseQuantity"
    else:
        result["quantity_source"] = "Missing"
    return result


def _safe_model_entities(model: Any) -> list[Any]:
    try:
        values = list(model)
    except Exception:
        values = []
    if values:
        return values
    by_type = getattr(model, "by_type", None)
    if not callable(by_type):
        return values
    for query in ("IfcProduct", "IfcObject"):
        try:
            values = list(by_type(query))
        except Exception:
            values = []
        if values:
            return values
    values = []
    seen: set[int] = set()
    for ifc_class in IFC_CLASSES:
        try:
            candidates = by_type(ifc_class)
        except Exception:
            continue
        for candidate in candidates:
            if id(candidate) not in seen:
                values.append(candidate)
                seen.add(id(candidate))
    return values


def _output_columns(config: ProjectConfig) -> tuple[str, ...]:
    try:
        configured = tuple(config.field_mapping["field_order"])
    except (AttributeError, KeyError, TypeError):
        configured = STANDARD_COLUMNS
    required = tuple(STANDARD_COLUMNS) + TRACE_COLUMNS
    result: list[str] = []
    for column in configured + required:
        if column not in result:
            result.append(column)
    return tuple(result)


def _empty_result(config: ProjectConfig) -> IfcReadResult:
    return IfcReadResult(pd.DataFrame(columns=_output_columns(config)), ())


def _close_model(model: Any) -> None:
    for name in ("close", "release", "dispose"):
        method = getattr(model, name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass
            return


def _extract_row(
    entity: Any,
    ifc_class: str,
    row_number: int,
    file_name: str,
    config: ProjectConfig,
    diagnostics: list[str],
) -> dict[str, Any]:
    info = _safe_info(entity)
    row: dict[str, Any] = {column: _MISSING for column in STANDARD_COLUMNS + TRACE_COLUMNS}
    row.update(
        {
            "source": "IFC",
            "ifc_class": ifc_class,
            "raw_row_number": row_number,
            "source_file": file_name,
        }
    )
    tags: list[str] = []
    category_mapping = config.category_mapping.get("ifc_class_to_category", {})
    category = category_mapping.get(ifc_class, _MISSING) if isinstance(category_mapping, Mapping) else _MISSING
    row["category"] = category
    row["guid"] = _text(_direct_value(entity, _GUID_KEYS, info))
    if _is_missing(row["guid"]):
        tags.append("missing_guid")
        diagnostics.append(f"Warning: 实体序号 {row_number} 缺少 GlobalId；请补充可追溯 GUID。")
    row["element_id"] = _text(_direct_value(entity, _ID_KEYS, info))
    row["element_name"] = _text(_direct_value(entity, _NAME_KEYS, info))
    if _is_missing(row["element_name"]):
        tags.append("missing_element_name")
    row["type_name"] = _extract_type_name(entity, info)
    if _is_missing(row["type_name"]):
        tags.append("missing_type_name")
    row["level"] = _extract_level(entity, info, config)
    if _is_missing(row["level"]):
        tags.append("missing_level")
        diagnostics.append(f"Warning: 实体序号 {row_number} 缺少楼层关系；请补充 IfcRelContainedInSpatialStructure。")
    material, multiple = _extract_material(entity, info, config)
    row["material"] = material
    if _is_missing(material):
        tags.append("missing_material")
    if multiple:
        tags.append("multiple_materials")
        diagnostics.append(f"Warning: 实体序号 {row_number} 关联多个材料；已稳定拼接显示名称。")
    quantities = _extract_quantities(entity, info, category, row_number, diagnostics, tags)
    row.update(quantities)
    row["quality_status"] = "Warning" if tags else "Pass"
    row["exception_tags"] = ";".join(tags) if tags else _MISSING
    return row


def read_ifc(path: Path, config: ProjectConfig) -> IfcReadResult:
    """Read supported IFC entities while keeping IfcOpenShell optional."""

    ifc_path = Path(path)
    file_name = ifc_path.name or "<unnamed>"
    try:
        if not ifc_path.is_file():
            raise IfcReaderError(f"IFC 文件不存在或不是普通文件：{file_name}；请检查输入路径。")
    except OSError as exc:
        raise IfcReaderError(f"IFC 文件检查失败：{file_name}；请确认文件可访问。") from exc

    try:
        ifcopenshell = importlib.import_module("ifcopenshell")
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        if (
            missing_name == "ifcopenshell"
            or missing_name.startswith("ifcopenshell.")
            or "ifcopenshell" in str(exc).casefold()
        ):
            raise IfcReaderUnavailable(
                "未安装可选 IFC 依赖；请运行 `pip install -r requirements-ifc.txt`，"
                "或继续使用 CSV 输入。"
            ) from exc
        raise IfcReaderError("IFC 依赖加载失败；请安装 requirements-ifc.txt 后重试。") from exc
    except Exception as exc:
        raise IfcReaderError("IFC 依赖加载失败；请安装 requirements-ifc.txt 后重试。") from exc

    model: Any = None
    diagnostics: list[str] = []
    rows: list[dict[str, Any]] = []
    try:
        try:
            model = ifcopenshell.open(str(ifc_path))
        except Exception as exc:
            raise IfcReaderError(
                f"IFC 文件打开失败：{file_name}；请确认文件完整且为有效 IFC。"
            ) from exc
        if model is None:
            raise IfcReaderError(f"IFC 文件打开失败：{file_name}；请确认文件完整且为有效 IFC。")
        try:
            entities = _safe_model_entities(model)
        except Exception as exc:
            raise IfcReaderError(
                f"IFC 实体遍历失败：{file_name}；请检查文件结构后重试。"
            ) from exc
        for row_number, entity in enumerate(entities, start=1):
            info = _safe_info(entity)
            ifc_class = _entity_class(entity, info)
            if ifc_class not in _SUPPORTED:
                shown = ifc_class or "未知"
                diagnostics.append(
                    f"Warning: 实体序号 {row_number} 的 IFC 类别 {shown} 不在六类支持范围内；已忽略。"
                )
                continue
            try:
                rows.append(_extract_row(entity, ifc_class, row_number, file_name, config, diagnostics))
            except Exception as exc:
                diagnostics.append(
                    f"Error: 实体序号 {row_number}（{ifc_class}）提取失败；已保留空值并继续读取。"
                )
                row = {
                    column: _MISSING for column in STANDARD_COLUMNS + TRACE_COLUMNS
                }
                row.update(
                    {
                        "source": "IFC",
                        "ifc_class": ifc_class,
                        "raw_row_number": row_number,
                        "source_file": file_name,
                        "exception_tags": "entity_error",
                        "quality_status": "Error",
                    }
                )
                rows.append(row)
    finally:
        if model is not None:
            _close_model(model)

    columns = _output_columns(config)
    frame = pd.DataFrame(rows, columns=columns)
    return IfcReadResult(frame=frame, diagnostics=tuple(diagnostics))


__all__ = [
    "IfcReaderError",
    "IfcReaderUnavailable",
    "IfcReadResult",
    "read_ifc",
]
