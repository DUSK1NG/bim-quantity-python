import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pytest

from src.config_loader import ConfigError, ProjectConfig, load_project_config

from src.schema import (
    QUALITY_STATUSES,
    QUANTITY_SOURCES,
    STANDARD_COLUMNS,
    validate_standard_dataframe,
)


def test_schema_constants_are_exact():
    assert STANDARD_COLUMNS == (
        "element_id",
        "guid",
        "source",
        "ifc_class",
        "category",
        "element_name",
        "type_name",
        "level",
        "material",
        "length_m",
        "area_m2",
        "volume_m3",
        "quantity",
        "unit",
        "unit_price",
        "total_cost",
        "quantity_source",
        "quality_status",
    )
    assert QUANTITY_SOURCES == (
        "IFC BaseQuantity",
        "Parameter Calculation",
        "CSV Schedule",
        "Missing",
    )
    assert QUALITY_STATUSES == ("Pass", "Warning", "Error")


def test_validate_standard_dataframe_reports_missing_columns():
    result = validate_standard_dataframe(pd.DataFrame({"guid": ["x"]}))
    assert result.valid is False
    assert "element_id" in result.missing_columns


@pytest.fixture()
def repo_config_dir() -> Path:
    return Path(__file__).parents[1] / "configs"


def test_load_project_config_returns_frozen_config(repo_config_dir: Path):
    config = load_project_config(repo_config_dir)
    assert isinstance(config, ProjectConfig)
    assert config.config_version == "2.0"
    with pytest.raises(Exception):
        config.config_version = "changed"


def test_all_phase_two_configs_load_without_unknown_top_level_keys(repo_config_dir: Path):
    config = load_project_config(repo_config_dir)
    assert set(config.field_mapping) == {"config_version", "aliases", "field_order"}
    assert set(config.category_mapping) == {
        "config_version", "canonical_categories", "ifc_class_to_category", "aliases",
    }
    assert set(config.level_mapping) == {"config_version", "canonical_levels", "aliases"}
    assert set(config.material_mapping) == {"config_version", "canonical_materials", "aliases"}
    assert set(config.naming_rules) == {"config_version", "allowed_patterns", "invalid_name_examples"}
    assert set(config.quality_rules) == {"config_version", "rules"}
    assert list(config.unit_prices.columns) == ["category", "material", "unit", "unit_price"]
    assert config.level_mapping["canonical_levels"] == ["一层", "二层", "三层"]
    assert set(config.category_mapping["canonical_categories"]) == {
        "Beam", "Column", "Slab", "Wall", "Door", "Window",
    }


def test_loader_rejects_missing_config_file(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    (bad_dir / "material_mapping.json").unlink()
    with pytest.raises(ConfigError, match="material_mapping.json"):
        load_project_config(bad_dir)


def test_loader_rejects_missing_config_version(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "level_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("config_version")
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="level_mapping.json.*config_version"):
        load_project_config(bad_dir)


def test_loader_rejects_unknown_top_level_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "quality_rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="quality_rules.json.*未知顶层键"):
        load_project_config(bad_dir)


def test_loader_rejects_duplicate_alias_in_any_mapping(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "material_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["aliases"]["钢材"].append(payload["aliases"]["混凝土"][0])
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="material_mapping.json.*重复别名"):
        load_project_config(bad_dir)


def test_loader_rejects_field_order_not_matching_schema(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "field_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["field_order"][0], payload["field_order"][1] = (
        payload["field_order"][1], payload["field_order"][0]
    )
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="field_mapping.json.*field_order.*STANDARD_COLUMNS"):
        load_project_config(bad_dir)


def test_loader_rejects_field_order_missing_schema_column(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "field_mapping.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["field_order"] = [name for name in payload["field_order"] if name != "quality_status"]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError, match="field_mapping.json.*field_order.*STANDARD_COLUMNS"):
        load_project_config(bad_dir)


def test_loader_rejects_wrong_unit_price_columns(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    prices = pd.read_csv(path)
    prices = prices.rename(columns={"unit_price": "price"})
    prices.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="sample_unit_prices.csv.*缺少列"):
        load_project_config(bad_dir)


def test_loader_rejects_wrong_unit_price_column_order(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    prices = pd.read_csv(path)[["category", "material", "unit_price", "unit"]]
    prices.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="sample_unit_prices.csv.*列顺序"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_unit_price(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "unit_price"] = -1
    frame.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="unit_price.*正数"):
        load_project_config(bad_dir)


def test_loader_rejects_non_numeric_unit_price(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    frame = pd.read_csv(path)
    frame["unit_price"] = frame["unit_price"].astype(object)
    frame.loc[0, "unit_price"] = "not-a-number"
    frame.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="unit_price.*正数"):
        load_project_config(bad_dir)


def _copied_config_dir(repo_config_dir: Path, tmp_path: Path) -> Path:
    """Return an isolated config tree for one negative-loader test."""

    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    return bad_dir


def _edit_json(
    config_dir: Path, filename: str, edit: Callable[[dict[str, Any]], None]
) -> None:
    path = config_dir / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    edit(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_loader_rejects_duplicate_field_order(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "field_mapping.json",
        lambda payload: payload["field_order"].__setitem__(
            -1, payload["field_order"][-2]
        ),
    )
    with pytest.raises(ConfigError, match="field_mapping.json.*field_order.*完全等于"):
        load_project_config(bad_dir)


def test_loader_rejects_extra_field_order_entry(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "field_mapping.json",
        lambda payload: payload["field_order"].append("unexpected"),
    )
    with pytest.raises(ConfigError, match="field_mapping.json.*field_order.*完全等于"):
        load_project_config(bad_dir)


def test_loader_rejects_missing_field_order_entry(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "field_mapping.json",
        lambda payload: payload["field_order"].pop(),
    )
    with pytest.raises(ConfigError, match="field_mapping.json.*field_order.*完全等于"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_category_canonical(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "category_mapping.json",
        lambda payload: payload["canonical_categories"].__setitem__(0, "Bogus"),
    )
    with pytest.raises(ConfigError, match="category_mapping.json.*canonical_categories"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_ifc_mapping_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["ifc_class_to_category"]["IfcUnknown"] = "Beam"

    _edit_json(bad_dir, "category_mapping.json", edit)
    with pytest.raises(ConfigError, match="category_mapping.json.*IFC"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_ifc_mapping_value(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["ifc_class_to_category"]["IfcBeam"] = "Column"

    _edit_json(bad_dir, "category_mapping.json", edit)
    with pytest.raises(ConfigError, match="category_mapping.json.*一对一"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_category_alias_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["aliases"]["Girder"] = payload["aliases"].pop("Beam")

    _edit_json(bad_dir, "category_mapping.json", edit)
    with pytest.raises(ConfigError, match="category_mapping.json.*aliases"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_level_canonical(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "level_mapping.json",
        lambda payload: payload["canonical_levels"].__setitem__(2, "四层"),
    )
    with pytest.raises(ConfigError, match="level_mapping.json.*canonical_levels"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_level_alias_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["aliases"]["四层"] = payload["aliases"].pop("一层")

    _edit_json(bad_dir, "level_mapping.json", edit)
    with pytest.raises(ConfigError, match="level_mapping.json.*aliases"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_material_canonical(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "material_mapping.json",
        lambda payload: payload["canonical_materials"].append("塑料"),
    )
    with pytest.raises(ConfigError, match="material_mapping.json.*canonical_materials"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_material_alias_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["aliases"]["塑料"] = payload["aliases"].pop("钢材")

    _edit_json(bad_dir, "material_mapping.json", edit)
    with pytest.raises(ConfigError, match="material_mapping.json.*aliases"):
        load_project_config(bad_dir)


def test_loader_rejects_invalid_naming_regex(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "naming_rules.json",
        lambda payload: payload["allowed_patterns"].__setitem__("IfcBeam", "["),
    )
    with pytest.raises(ConfigError, match="naming_rules.json.*正则"):
        load_project_config(bad_dir)


def test_loader_rejects_empty_invalid_name_example(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "naming_rules.json",
        lambda payload: payload["invalid_name_examples"].clear(),
    )
    with pytest.raises(ConfigError, match="naming_rules.json.*invalid_name_examples"):
        load_project_config(bad_dir)


def test_loader_rejects_bogus_quality_severity(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)
    _edit_json(
        bad_dir,
        "quality_rules.json",
        lambda payload: payload["rules"][0].__setitem__("severity", "Bogus"),
    )
    with pytest.raises(ConfigError, match="quality_rules.json.*severity"):
        load_project_config(bad_dir)


def test_loader_rejects_duplicate_quality_rule_id(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["rules"][1]["id"] = payload["rules"][0]["id"]

    _edit_json(bad_dir, "quality_rules.json", edit)
    with pytest.raises(ConfigError, match="quality_rules.json.*重复.*id"):
        load_project_config(bad_dir)


def test_loader_rejects_unknown_quality_rule_id(repo_config_dir: Path, tmp_path: Path):
    bad_dir = _copied_config_dir(repo_config_dir, tmp_path)

    def edit(payload):
        payload["rules"][0]["id"] = "not_a_planned_rule"

    _edit_json(bad_dir, "quality_rules.json", edit)
    with pytest.raises(ConfigError, match="quality_rules.json.*未知.*id"):
        load_project_config(bad_dir)


def test_loader_rejects_duplicate_unit_price_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    frame = pd.read_csv(path)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="重复 category/material/unit"):
        load_project_config(bad_dir)


def test_current_outputs_and_docs_exist():
    """The checked-in foundation has current artifacts and no later module."""

    root = Path(__file__).parents[1]
    required = [
        root / "README.md",
        root / "requirements.txt",
        root / "requirements-ifc.txt",
        root / "pyproject.toml",
        root / "src" / "schema.py",
        root / "src" / "config_loader.py",
        root / "scripts" / "generate_sample_data.py",
        root / "data" / "sample" / "README.md",
        root / "docs" / "data_dictionary.md",
        root / "docs" / "technical_route.md",
        root / "assets" / "README.md",
        root / "data" / "raw" / ".gitkeep",
        root / "data" / "processed" / ".gitkeep",
        root / "outputs" / "excel" / ".gitkeep",
        root / "outputs" / "charts" / ".gitkeep",
        root / "outputs" / "reports" / ".gitkeep",
    ]
    assert all(path.is_file() for path in required)

    forbidden = [
        root / "src" / "quantity_calculator.py",
        root / "src" / "cost_calculator.py",
        root / "src" / "quality_checker.py",
        root / "src" / "validation.py",
        root / "src" / "report_generator.py",
        root / "src" / "pipeline.py",
        root / "src" / "ifc_reader.py",
        root / "app" / "streamlit_app.py",
        root / "scripts" / "run_pipeline.py",
        root / "scripts" / "export_report.py",
    ]
    assert all(not path.exists() for path in forbidden)


def test_root_readme_describes_current_phase_two_capabilities():
    """README must expose the delivered generator and defer later modules."""

    text = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    assert "Python 3.10/3.11" in text
    assert "Windows 10/11" in text
    assert "scripts/generate_sample_data.py" in text
    assert "-m pytest -q" in text
    assert "20260804" in text
    assert "240" in text
    for label in (
        "一层",
        "二层",
        "三层",
        "IfcBeam",
        "IfcColumn",
        "IfcSlab",
        "IfcWall",
        "IfcDoor",
        "IfcWindow",
    ):
        assert label in text
    assert "程序演示数据" in text
    assert "本项目单价为教学示例数据，不用于正式工程造价。" in text
    assert "CSV reader" in text
    assert "Streamlit" in text
    assert "IFC reader" in text
    assert "planned for Task 3" not in text
    assert "not available in this task" not in text
