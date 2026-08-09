"""Contract tests for the optional IFC reader boundary and extraction."""

from __future__ import annotations

import importlib
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from src.config_loader import ProjectConfig, load_project_config
from src.schema import IFC_CLASSES
from tests.fixtures.fake_ifc import FakeEntity, make_fake_module, six_supported_entities


ROOT = Path(__file__).parents[1]


@pytest.fixture()
def config() -> ProjectConfig:
    return load_project_config(ROOT / "configs")


def _reader_module():
    return importlib.import_module("src.ifc_reader")


def test_importing_reader_keeps_ifcopenshell_lazy() -> None:
    sys.modules.pop("ifcopenshell", None)
    _reader_module()
    assert "ifcopenshell" not in sys.modules


def test_missing_optional_dependency_is_actionable(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = _reader_module()
    model_path = tmp_path / "model.ifc"
    model_path.write_text("IFC", encoding="utf-8")
    original_import = reader.importlib.import_module

    def missing(name: str, package: str | None = None) -> ModuleType:
        if name == "ifcopenshell":
            raise ModuleNotFoundError("No module named 'ifcopenshell'", name=name)
        return original_import(name, package)

    monkeypatch.setattr(reader.importlib, "import_module", missing)
    with pytest.raises(reader.IfcReaderUnavailable, match="requirements-ifc.txt"):
        reader.read_ifc(model_path, config)


def test_missing_path_has_chinese_repair_hint(tmp_path: Path, config: ProjectConfig) -> None:
    reader = _reader_module()
    with pytest.raises(reader.IfcReaderError, match=r"文件.*不存在|请"):
        reader.read_ifc(tmp_path / "missing.ifc", config)


def test_ifc_read_result_is_frozen_and_empty_model_has_contract_columns(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = _reader_module()
    fake_module, model = make_fake_module([])
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "empty.ifc"
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)

    assert result.frame.empty
    assert tuple(result.frame.columns) == tuple(config.field_mapping["field_order"])
    assert isinstance(result.diagnostics, tuple)
    assert model.closed is True
    with pytest.raises(FrozenInstanceError):
        result.diagnostics = ()  # type: ignore[misc]


def test_reader_extracts_six_classes_and_traceable_standard_rows(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = _reader_module()
    entities = six_supported_entities()
    fake_module, model = make_fake_module(entities + [FakeEntity("IfcProject", Name="unknown")])
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "nested" / "teaching-model.ifc"
    model_path.parent.mkdir()
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)
    frame = result.frame

    assert tuple(frame.columns) == tuple(config.field_mapping["field_order"])
    assert len(frame) == 6
    assert set(frame["ifc_class"]) == set(IFC_CLASSES)
    assert frame["source"].eq("IFC").all()
    assert frame["source_file"].eq(model_path.name).all()
    assert frame["raw_row_number"].tolist() == list(range(1, 7))
    assert frame["guid"].tolist() == [f"G-{name.upper()}" for name in ("beam", "column", "slab", "wall", "door", "window")]
    assert frame["category"].tolist() == ["Beam", "Column", "Slab", "Wall", "Door", "Window"]
    assert frame["level"].notna().all()
    assert frame["material"].tolist()[:3] == ["混凝土", "钢材", "混凝土"]
    assert frame["length_m"].eq(2.5).all()
    assert frame["area_m2"].eq(3.5).all()
    assert frame["volume_m3"].eq(4.5).all()
    assert frame["quantity"].eq(6.5).all()
    assert frame["quantity_source"].eq("IFC BaseQuantity").all()
    assert any(item.startswith("Warning: ") for item in result.diagnostics)
    assert model.closed is True


def test_bad_quantities_and_malformed_entity_do_not_stop_remaining_rows(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = _reader_module()
    entities = six_supported_entities()
    entities[1].BaseQuantities = {"Length": -2, "Area": float("inf"), "Volume": "bad", "Quantity": -1}
    entities[2].GlobalId = None
    entities.insert(3, FakeEntity("IfcWall", GlobalId="G-MALFORMED", Name="bad", get_info_raises=True))
    fake_module, _model = make_fake_module(entities)
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "bad-values.ifc"
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)

    assert len(result.frame) == 7
    assert result.frame["ifc_class"].tolist().count("IfcWall") == 2
    assert result.frame.loc[result.frame["guid"].eq("G-COLUMN"), "quantity"].isna().all()
    assert any(item.startswith("Warning: ") for item in result.diagnostics)
    assert result.frame["raw_row_number"].tolist() == list(range(1, 8))


def test_base_quantity_without_explicit_unit_stays_missing(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A category name must not silently invent a unit for IFC quantities."""

    reader = _reader_module()
    entity = six_supported_entities()[0]
    entity.Unit = None
    entity._attrs["Unit"] = None
    fake_module, _model = make_fake_module([entity])
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "unitless.ifc"
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)
    row = result.frame.iloc[0]

    assert pd.isna(row["unit"])
    assert pd.isna(row["quantity"])
    assert row["quantity_source"] == "Missing"
    assert any("单位" in item for item in result.diagnostics)


def test_unknown_base_quantity_unit_does_not_leak_unconverted_values(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown units keep raw provenance but clear every affected SI value."""

    reader = _reader_module()
    entity = six_supported_entities()[0]
    entity.Unit = "ft"
    fake_module, _model = make_fake_module([entity])
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "unknown-unit.ifc"
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)
    row = result.frame.iloc[0]

    assert row["raw_unit"] == "ft"
    assert pd.isna(row["unit"])
    for column in ("length_m", "area_m2", "volume_m3", "quantity"):
        assert pd.isna(row[column]), column
    assert row["quantity_source"] == "Missing"
    assert any(item.startswith("Warning: ") and "单位" in item for item in result.diagnostics)


def test_entity_extraction_fallback_marks_quantity_source_missing(
    tmp_path: Path, config: ProjectConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row retained after an extraction exception cannot claim IFC quantity."""

    class ExplodingEntity:
        def is_a(self, name: str | None = None):
            return "IfcBeam" if name is None else name == "IfcBeam"

        def get_info(self):
            raise RuntimeError("malformed fake entity")

        @property
        def GlobalId(self):
            raise RuntimeError("malformed fake entity")

    reader = _reader_module()
    fake_module, _model = make_fake_module([ExplodingEntity()])
    monkeypatch.setitem(sys.modules, "ifcopenshell", fake_module)
    model_path = tmp_path / "malformed.ifc"
    model_path.write_text("IFC", encoding="utf-8")

    result = reader.read_ifc(model_path, config)
    row = result.frame.iloc[0]

    assert row["quantity_source"] == "Missing"
    assert row["quality_status"] == "Error"
    assert any(item.startswith("Error: ") for item in result.diagnostics)
