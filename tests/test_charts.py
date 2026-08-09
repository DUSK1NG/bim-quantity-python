"""Contract tests for the stage 3.4 Plotly chart utilities."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.quality_report import QualityIssue, QualityReport
from src.validation import ValidationResult


def _summary_frames() -> dict[str, pd.DataFrame]:
    """Return intentionally unsorted stage 3.3-style summary tables."""

    return {
        "by_level": pd.DataFrame(
            {
                "level": ["三层", "一层", "二层"],
                "element_count": [3, 1, 2],
                "quantity_sum": [7.0, 2.0, 4.0],
                "volume_sum": [1.5, 0.5, 1.0],
                "total_cost": [300.0, 100.0, 200.0],
            }
        ),
        "by_category": pd.DataFrame(
            {
                "category": ["Wall", "Beam", "Column"],
                "quantity_sum": [5.0, 2.0, 3.0],
                "element_count": [5, 2, 3],
            }
        ),
        "by_material": pd.DataFrame(
            {
                "material": ["木材", "混凝土", "钢材"],
                "quantity_sum": [2.0, 8.0, 3.0],
            }
        ),
        "cost_summary": pd.DataFrame(
            {
                "category": ["Wall", "Beam", "Beam"],
                "material": ["混凝土", "钢材", "混凝土"],
                "unit": ["m³", "kg", "m³"],
                "total_cost": [1200.0, 300.0, 700.0],
            }
        ),
    }


def _quality_report() -> QualityReport:
    return QualityReport(
        total_rows=5,
        issue_rows=3,
        clean_rows=2,
        counts_by_rule={"missing_level": 2, "missing_material": 1},
        counts_by_severity={"Warning": 2, "Error": 1},
        not_applicable_rules=(),
        issues=(
            QualityIssue(2, "missing_level", "Warning", "level", "缺失楼层"),
            QualityIssue(3, "missing_material", "Error", "material", "缺失材料"),
        ),
    )


def _validation_result() -> ValidationResult:
    details = pd.DataFrame(
        {
            "category": ["Wall", "Beam"],
            "absolute_error": [0.2, 0.1],
            "relative_error_pct": [10.0, 5.0],
        }
    )
    summary = pd.DataFrame(
        {
            "category": ["Wall", "Beam"],
            "count": [1, 1],
            "mean_absolute_error": [0.2, 0.1],
            "max_absolute_error": [0.2, 0.1],
            "mean_relative_error_pct": [10.0, 5.0],
            "max_relative_error_pct": [10.0, 5.0],
        }
    )
    return ValidationResult(details=details, summary_by_category=summary)


def _title_text(fig: go.Figure) -> str:
    return str(fig.layout.title.text or "")


def test_all_chart_functions_return_chinese_nonempty_figures() -> None:
    """Each chart has data, a Chinese title, and unit-aware labels/hover text."""

    from app.utils.charts import (
        fig_concrete_volume_by_level,
        fig_cost_distribution,
        fig_elements_by_level,
        fig_material_usage,
        fig_quality_issue_counts,
        fig_quantity_share_by_category,
        fig_validation_error,
    )

    frames = _summary_frames()
    figures = (
        fig_elements_by_level(frames["by_level"]),
        fig_concrete_volume_by_level(frames["by_level"]),
        fig_quantity_share_by_category(frames["by_category"]),
        fig_material_usage(frames["by_material"]),
        fig_cost_distribution(frames["cost_summary"]),
        fig_quality_issue_counts(_quality_report()),
        fig_validation_error(_validation_result()),
    )

    assert all(isinstance(figure, go.Figure) for figure in figures)
    assert all(figure.data for figure in figures)
    assert all(any("\u4e00" <= char <= "\u9fff" for char in _title_text(figure)) for figure in figures)
    assert all(
        any(
            "\u4e00" <= char <= "\u9fff"
            for trace in figure.data
            for char in str(getattr(trace, "hovertemplate", ""))
        )
        for figure in figures
    )

    assert fig_elements_by_level(frames["by_level"]).layout.xaxis.title.text == "楼层"
    assert "个" in str(fig_elements_by_level(frames["by_level"]).layout.yaxis.title.text)
    assert "m³" in str(fig_concrete_volume_by_level(frames["by_level"]).layout.yaxis.title.text)
    assert "元" in str(fig_cost_distribution(frames["cost_summary"]).layout.yaxis.title.text)


def test_chart_categories_use_deterministic_canonical_sorting() -> None:
    from app.utils.charts import (
        fig_concrete_volume_by_level,
        fig_cost_distribution,
        fig_elements_by_level,
        fig_material_usage,
        fig_quantity_share_by_category,
    )

    frames = _summary_frames()
    assert list(fig_elements_by_level(frames["by_level"]).data[0].x) == ["一层", "二层", "三层"]
    assert list(fig_concrete_volume_by_level(frames["by_level"]).data[0].x) == ["一层", "二层", "三层"]
    assert list(fig_quantity_share_by_category(frames["by_category"]).data[0].labels) == [
        "Beam",
        "Column",
        "Wall",
    ]
    assert list(fig_material_usage(frames["by_material"]).data[0].x) == ["混凝土", "钢材", "木材"]
    cost_labels = list(fig_cost_distribution(frames["cost_summary"]).data[0].x)
    assert cost_labels == ["Beam / 混凝土 / m³", "Beam / 钢材 / kg", "Wall / 混凝土 / m³"]


def test_all_chart_functions_return_annotated_empty_figures_for_empty_or_missing_data() -> None:
    from app.utils.charts import (
        fig_concrete_volume_by_level,
        fig_cost_distribution,
        fig_elements_by_level,
        fig_material_usage,
        fig_quality_issue_counts,
        fig_quantity_share_by_category,
        fig_validation_error,
    )

    empty = pd.DataFrame()
    empty_validation = ValidationResult(
        details=pd.DataFrame(), summary_by_category=pd.DataFrame()
    )
    empty_report = QualityReport(
        total_rows=0,
        issue_rows=0,
        clean_rows=0,
        counts_by_rule={},
        counts_by_severity={},
        not_applicable_rules=(),
        issues=(),
    )
    figures = (
        fig_elements_by_level(empty),
        fig_concrete_volume_by_level(empty),
        fig_quantity_share_by_category(empty),
        fig_material_usage(empty),
        fig_cost_distribution(empty),
        fig_quality_issue_counts(empty_report),
        fig_validation_error(empty_validation),
        fig_elements_by_level(pd.DataFrame({"level": ["一层"]})),
    )

    for figure in figures:
        assert isinstance(figure, go.Figure)
        assert not figure.data
        assert "暂无可展示数据" in " ".join(str(annotation.text) for annotation in figure.layout.annotations)
