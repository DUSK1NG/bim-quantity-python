import json
import shutil
from pathlib import Path

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


def test_loader_rejects_duplicate_unit_price_key(repo_config_dir: Path, tmp_path: Path):
    bad_dir = tmp_path / "configs"
    shutil.copytree(repo_config_dir, bad_dir)
    path = bad_dir / "sample_unit_prices.csv"
    frame = pd.read_csv(path)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_csv(path, index=False)
    with pytest.raises(ConfigError, match="重复 category/material/unit"):
        load_project_config(bad_dir)
