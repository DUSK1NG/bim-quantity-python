"""Tiny IfcOpenShell-shaped objects used by the reader contract tests.

The production reader deliberately only depends on the small object protocol
exposed by these fakes (``open``, ``by_type``, and a few explicit attributes),
so the tests never need a real IFC binary or an installed IfcOpenShell wheel.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Iterable


class FakeEntity:
    """A permissive IFC entity with attributes and explicit IFC type."""

    def __init__(self, ifc_class: str, **attrs: Any) -> None:
        self._ifc_class = ifc_class
        self._attrs = dict(attrs)
        for key, value in attrs.items():
            setattr(self, key, value)

    def is_a(self, name: str | None = None) -> str | bool:
        if name is None:
            return self._ifc_class
        return self._ifc_class == name

    def get_info(self) -> dict[str, Any]:
        return {"type": self._ifc_class, **self._attrs}


class FakeModel:
    """In-memory model returned from ``ifcopenshell.open``."""

    def __init__(self, entities: Iterable[FakeEntity]) -> None:
        self.entities = list(entities)
        self.closed = False

    def by_type(self, ifc_class: str) -> list[FakeEntity]:
        return [entity for entity in self.entities if entity.is_a(ifc_class)]

    def __iter__(self):
        return iter(self.entities)

    def close(self) -> None:
        self.closed = True


def make_fake_module(entities: Iterable[FakeEntity]) -> tuple[ModuleType, FakeModel]:
    """Return a module-like fake and its model for ``sys.modules`` injection."""

    model = FakeModel(entities)
    module = ModuleType("ifcopenshell")
    module.open = lambda _path: model  # type: ignore[attr-defined]
    return module, model


def six_supported_entities() -> list[FakeEntity]:
    """Build one entity for each supported class with explicit source data."""

    values = {
        "IfcBeam": ("G-BEAM", "E-BEAM", "梁示例", "梁类型", "一层", "混凝土", "m"),
        "IfcColumn": ("G-COLUMN", "E-COLUMN", "柱示例", "柱类型", "二层", "钢材", "m³"),
        "IfcSlab": ("G-SLAB", "E-SLAB", "板示例", "板类型", "三层", "混凝土", "m³"),
        "IfcWall": ("G-WALL", "E-WALL", "墙示例", "墙类型", "一层", "砖材", "m³"),
        "IfcDoor": ("G-DOOR", "E-DOOR", "门示例", "门类型", "二层", "木材", "樘"),
        "IfcWindow": ("G-WINDOW", "E-WINDOW", "窗示例", "窗类型", "三层", "玻璃", "樘"),
    }
    entities: list[FakeEntity] = []
    for ifc_class, (guid, element_id, name, type_name, level, material, unit) in values.items():
        entities.append(
            FakeEntity(
                ifc_class,
                GlobalId=guid,
                ElementId=element_id,
                Name=name,
                ObjectType=type_name,
                Level=level,
                Material=material,
                BaseQuantities={
                    "Length": 2.5,
                    "Area": 3.5,
                    "Volume": 4.5,
                    "Count": 1.0,
                    "Quantity": 6.5,
                },
                Unit=unit,
            )
        )
    return entities

