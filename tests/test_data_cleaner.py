"""Contract tests for the configuration-driven stage 3 data cleaner."""

from __future__ import annotations

import importlib
from itertools import combinations
from pathlib import Path

import pandas as pd
import pytest

from src.config_loader import load_project_config
from src.csv_reader import read_elements_csv


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"
SAMPLE = ROOT / "data" / "sample" / "sample_elements.csv"


def _cleaner_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.data_cleaner")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"data cleaner module is not available yet: {exc}")


@pytest.fixture()
def config():
    return load_project_config(CONFIG_DIR)


@pytest.fixture()
def sample_frame():
    return read_elements_csv(SAMPLE)


def test_clean_elements_recomputes_disjoint_sample_anomalies(config, sample_frame):
    cleaner = _cleaner_module()

    result = cleaner.clean_elements(sample_frame, config)

    assert len(result.frame) == 240
    assert result.report.counts_by_rule == {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid": 4,
        "zero_quantity": 4,
        "invalid_name": 3,
        "unknown_unit": 2,
        "unmatched_unit_price": 2,
    }
    assert result.report.not_applicable_rules == (
        "missing_section_size",
        "outlier_dimension",
    )

    rows_by_rule = {
        rule_id: {
            issue.raw_row_number
            for issue in result.report.issues
            if issue.rule_id == rule_id
        }
        for rule_id in result.report.counts_by_rule
    }
    assert {rule: len(rows) for rule, rows in rows_by_rule.items()} == {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid": 4,
        "zero_quantity": 4,
        "invalid_name": 3,
        "unknown_unit": 2,
        "unmatched_unit_price": 2,
    }
    for left, right in combinations(rows_by_rule.values(), 2):
        assert left.isdisjoint(right)

    duplicate_guid = result.frame.loc[
        result.frame["guid"].duplicated(keep=False), "guid"
    ]
    assert duplicate_guid.nunique() == 2
    assert sorted(duplicate_guid.value_counts().tolist()) == [2, 2]


def test_clean_elements_maps_aliases_and_blank_strings_to_missing(config):
    cleaner = _cleaner_module()
    frame = pd.DataFrame(
        {
            "构件ID": [" E-1 "],
            "全局唯一标识": [" GUID-1 "],
            "source": ["CSV"],
            "ifc_class": ["IfcBeam"],
            "类别": [" 梁 "],
            "族名称": [" 梁-AA-001 "],
            "类型": [" IfcBeam-Standard "],
            "楼层": [" Level 1 "],
            "材料": [" Concrete "],
            "长度": ["1.5"],
            "面积": ["2.5"],
            "体积": ["3.5"],
            "数量": ["3.5"],
            "单位": [" m³ "],
            "unit_price": [""],
            "total_cost": [""],
            "quantity_source": ["CSV Schedule"],
            "quality_status": ["Error"],
            "raw_row_number": [17],
            "source_file": [r"C:\imports\alias.csv"],
        }
    )

    result = cleaner.clean_elements(frame, config)
    row = result.frame.iloc[0]

    assert row["element_id"] == "E-1"
    assert row["guid"] == "GUID-1"
    assert row["category"] == "Beam"
    assert row["level"] == "一层"
    assert row["material"] == "混凝土"
    assert row["quantity"] == pytest.approx(3.5)
    assert row["unit"] == "m³"
    assert row["unit_price"] == pytest.approx(520.0)
    assert row["total_cost"] == pytest.approx(1820.0)
    assert row["quality_status"] == "Pass"
    assert pd.isna(result.frame.loc[0, "raw_unit"]) is False
    assert result.frame.loc[0, "raw_unit"] == " m³ "


def test_clean_elements_rejects_non_numeric_values_with_traceability(
    config, sample_frame
):
    cleaner = _cleaner_module()
    broken = sample_frame.iloc[[0]].copy()
    broken["quantity"] = "not-a-number"
    broken["source_file"] = r"C:\imports\bad.csv"
    broken["raw_row_number"] = 91

    with pytest.raises(
        cleaner.DataCleaningError,
        match=r"quantity.*bad\.csv.*raw_row_number.?91",
    ):
        cleaner.clean_elements(broken, config)


def test_clean_elements_recomputes_quality_status_and_keeps_problem_rows(
    config, sample_frame
):
    cleaner = _cleaner_module()
    changed = sample_frame.iloc[[100, 101, 102]].copy()
    changed.loc[100, "quality_status"] = "Error"
    changed.loc[101, "quantity"] = 0
    changed.loc[102, "quantity"] = -1

    result = cleaner.clean_elements(changed, config)

    assert len(result.frame) == len(changed)
    assert result.frame.loc[100, "quality_status"] == "Pass"
    assert result.frame.loc[101, "quality_status"] == "Warning"
    assert result.frame.loc[102, "quality_status"] == "Error"
    assert result.report.issue_rows == 2
    assert result.report.clean_rows == len(changed) - 2


def test_clean_elements_retains_unknown_values_and_unmatched_prices(config, sample_frame):
    cleaner = _cleaner_module()
    changed = sample_frame.iloc[[0]].copy()
    changed["material"] = "未知材料"
    changed["unit_price"] = 999
    changed["total_cost"] = 999

    result = cleaner.clean_elements(changed, config)

    assert result.frame.loc[0, "material"] == "未知材料"
    assert pd.isna(result.frame.loc[0, "unit_price"])
    assert pd.isna(result.frame.loc[0, "total_cost"])
    assert result.report.counts_by_rule == {"unmatched_unit_price": 1}
