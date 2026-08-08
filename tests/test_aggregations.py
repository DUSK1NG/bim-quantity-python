"""Contract tests for the stage 3.3 deterministic aggregation helpers."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.quality_report import DISCLAIMER, QualityIssue, QualityReport


SUMMARY_COLUMNS = (
    "level",
    "element_count",
    "quantity_sum",
    "area_sum",
    "volume_sum",
    "total_cost",
)
GROUP_SUMMARY_COLUMNS = (
    "category",
    "element_count",
    "quantity_sum",
    "area_sum",
    "volume_sum",
    "total_cost",
)
MATERIAL_SUMMARY_COLUMNS = (
    "material",
    "element_count",
    "quantity_sum",
    "area_sum",
    "volume_sum",
    "total_cost",
)
COST_SUMMARY_COLUMNS = (
    "category",
    "material",
    "unit",
    "element_count",
    "quantity_sum",
    "area_sum",
    "volume_sum",
    "total_cost",
)


def _aggregations_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.aggregations")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"aggregations module is not available yet: {exc}")


@pytest.fixture()
def frame() -> pd.DataFrame:
    """A small table covering valid, missing, duplicate and invalid values."""

    return pd.DataFrame(
        {
            "element_id": ["E1", "E2", "E1", "", pd.NA],
            "level": ["一层", "一层", "二层", pd.NA, "二层"],
            "category": ["Beam", "Beam", "Wall", "Door", "Door"],
            "material": ["混凝土", "混凝土", pd.NA, "木材", pd.NA],
            "unit": ["m", "m", "m³", "樘", "樘"],
            "quantity": [2.0, 1.0, 3.0, -4.0, pd.NA],
            "area_m2": [3.0, 2.0, 1.0, float("inf"), 0.0],
            "volume_m3": [4.0, 5.0, 2.0, -1.0, 1.0],
            "total_cost": [10.0, 20.0, 30.0, -40.0, float("inf")],
        }
    )


def test_fixed_rows_are_summarized_by_level_category_and_material(frame: pd.DataFrame) -> None:
    aggregations = _aggregations_module()

    by_level = aggregations.summarize_by_level(frame).set_index("level")
    assert tuple(by_level.reset_index().columns) == SUMMARY_COLUMNS
    assert by_level.loc["一层", "element_count"] == 2
    assert by_level.loc["一层", "quantity_sum"] == pytest.approx(3.0)
    assert by_level.loc["一层", "area_sum"] == pytest.approx(5.0)
    assert by_level.loc["一层", "volume_sum"] == pytest.approx(9.0)
    assert by_level.loc["一层", "total_cost"] == pytest.approx(30.0)
    assert by_level.loc["二层", "element_count"] == 1
    assert by_level.loc["二层", "quantity_sum"] == pytest.approx(3.0)
    assert by_level.loc["二层", "area_sum"] == pytest.approx(1.0)
    assert by_level.loc["二层", "volume_sum"] == pytest.approx(3.0)
    assert by_level.loc["二层", "total_cost"] == pytest.approx(30.0)
    assert by_level.loc["未分类", "element_count"] == 0
    assert pd.isna(by_level.loc["未分类", "quantity_sum"])

    by_category = aggregations.summarize_by_category(frame).set_index("category")
    assert tuple(by_category.reset_index().columns) == GROUP_SUMMARY_COLUMNS
    assert by_category.loc["Beam", "element_count"] == 2
    assert by_category.loc["Beam", "quantity_sum"] == pytest.approx(3.0)
    assert by_category.loc["Beam", "area_sum"] == pytest.approx(5.0)
    assert by_category.loc["Beam", "volume_sum"] == pytest.approx(9.0)
    assert by_category.loc["Beam", "total_cost"] == pytest.approx(30.0)
    assert by_category.loc["Wall", "element_count"] == 1
    assert by_category.loc["Wall", "total_cost"] == pytest.approx(30.0)
    assert by_category.loc["Door", "element_count"] == 0
    assert pd.isna(by_category.loc["Door", "total_cost"])

    by_material = aggregations.summarize_by_material(frame).set_index("material")
    assert tuple(by_material.reset_index().columns) == MATERIAL_SUMMARY_COLUMNS
    assert by_material.loc["混凝土", "element_count"] == 2
    assert by_material.loc["混凝土", "quantity_sum"] == pytest.approx(3.0)
    assert by_material.loc["混凝土", "area_sum"] == pytest.approx(5.0)
    assert by_material.loc["混凝土", "volume_sum"] == pytest.approx(9.0)
    assert by_material.loc["混凝土", "total_cost"] == pytest.approx(30.0)
    assert by_material.loc["未分类", "element_count"] == 1
    assert by_material.loc["未分类", "quantity_sum"] == pytest.approx(3.0)


def test_cost_summary_groups_category_material_and_unit_and_ignores_bad_amounts(
    frame: pd.DataFrame,
) -> None:
    aggregations = _aggregations_module()

    result = aggregations.summarize_costs(frame)

    assert tuple(result.columns) == COST_SUMMARY_COLUMNS
    beam = result.loc[
        (result["category"] == "Beam")
        & (result["material"] == "混凝土")
        & (result["unit"] == "m")
    ].iloc[0]
    assert beam["element_count"] == 2
    assert beam["quantity_sum"] == pytest.approx(3.0)
    assert beam["area_sum"] == pytest.approx(5.0)
    assert beam["volume_sum"] == pytest.approx(9.0)
    assert beam["total_cost"] == pytest.approx(30.0)

    bad_door = result.loc[
        (result["category"] == "Door") & (result["material"] == "木材")
    ].iloc[0]
    assert bad_door["element_count"] == 0
    assert pd.isna(bad_door["total_cost"])


def test_empty_frames_return_fixed_columns_for_every_summary() -> None:
    aggregations = _aggregations_module()
    empty = pd.DataFrame()

    assert tuple(aggregations.summarize_by_level(empty).columns) == SUMMARY_COLUMNS
    assert tuple(aggregations.summarize_by_category(empty).columns) == GROUP_SUMMARY_COLUMNS
    assert tuple(aggregations.summarize_by_material(empty).columns) == MATERIAL_SUMMARY_COLUMNS
    assert tuple(aggregations.summarize_costs(empty).columns) == COST_SUMMARY_COLUMNS
    assert aggregations.summarize_by_level(empty).empty
    assert aggregations.summarize_costs(empty).empty


def test_build_overview_counts_trusted_ids_and_sums_only_valid_values(
    frame: pd.DataFrame,
) -> None:
    aggregations = _aggregations_module()
    report = QualityReport(
        total_rows=len(frame),
        issue_rows=2,
        clean_rows=len(frame) - 2,
        counts_by_rule={"missing_level": 1},
        counts_by_severity={"Warning": 1},
        not_applicable_rules=(),
        issues=(QualityIssue(4, "missing_level", "Warning", "level", "缺失楼层"),),
    )

    original = frame.copy(deep=True)
    overview = aggregations.build_overview(
        frame,
        report,
        r"C:\imports\sample_elements.csv",
    )

    assert overview == {
        "source_file": "sample_elements.csv",
        "total_rows": 5,
        "element_count": 2,
        "category_count": 3,
        "level_count": 2,
        "area_sum": pytest.approx(6.0),
        "volume_sum": pytest.approx(12.0),
        "issue_rows": 2,
        "total_cost": pytest.approx(60.0),
        "disclaimer": DISCLAIMER,
    }
    pd.testing.assert_frame_equal(frame, original)
