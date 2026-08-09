"""Small, deterministic Plotly figures for the Streamlit dashboard.

The functions in this module deliberately consume the summaries produced by
``src.aggregations`` (or the immutable quality/validation result objects).
They do not recalculate quantities, costs, or quality rules.  A missing or
empty input produces a useful empty figure instead of an exception so that a
page can render before a pipeline run has completed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.quality_report import QualityReport
from src.validation import ValidationResult


_NO_DATA = "暂无可展示数据"

_LEVEL_ORDER = {"一层": 0, "二层": 1, "三层": 2}
_CATEGORY_ORDER = {
    "Beam": 0,
    "Column": 1,
    "Slab": 2,
    "Wall": 3,
    "Door": 4,
    "Window": 5,
}
_MATERIAL_ORDER = {
    "混凝土": 0,
    "钢材": 1,
    "木材": 2,
    "玻璃": 3,
    "铝合金": 4,
}


def _is_missing(value: Any) -> bool:
    """Return whether a scalar has pandas-style missing semantics."""

    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    # numpy.bool_ does not inherit from bool, while list/array values are not
    # valid chart labels.  ``bool`` is safe for scalar numpy values only.
    try:
        if getattr(missing, "ndim", 0) == 0:
            return bool(missing)
    except (TypeError, ValueError):
        pass
    return False


def _display_label(value: Any) -> str:
    """Return a safe, readable category label for an axis or legend."""

    if _is_missing(value):
        return "未分类"
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or "未分类"
    return str(value)


def _finite_number(value: Any) -> float | None:
    """Convert one chart value to a finite float, otherwise return ``None``."""

    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _empty_figure(
    title: str,
    *,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
    legend_title: str | None = None,
) -> go.Figure:
    """Build the shared, annotated figure used for empty/malformed inputs."""

    figure = go.Figure()
    figure.update_layout(
        template="plotly_white",
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        legend_title_text=legend_title,
    )
    figure.add_annotation(
        text=_NO_DATA,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16},
    )
    return figure


def _require_frame(frame: pd.DataFrame, argument_name: str) -> pd.DataFrame:
    """Copy a DataFrame and make a named index available as a normal column."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{argument_name} 必须是 pandas DataFrame。")
    result = frame.copy(deep=True)
    return result


def _with_column(frame: pd.DataFrame, column: str) -> pd.DataFrame | None:
    """Return ``frame`` with an index-named grouping column when possible."""

    if column in frame.columns:
        return frame
    if frame.index.name == column:
        try:
            return frame.reset_index()
        except ValueError:
            return None
    return None


def _sort_rank(value: str, order: Mapping[str, int]) -> int:
    return int(order.get(value, len(order) + 1000))


def _prepare_metric(
    frame: pd.DataFrame,
    *,
    label_column: str,
    value_column: str,
    argument_name: str,
    order: Mapping[str, int] | None = None,
) -> pd.DataFrame | None:
    """Select one precomputed metric and sort labels deterministically."""

    source = _with_column(_require_frame(frame, argument_name), label_column)
    if source is None or value_column not in source.columns:
        return None

    labels = source[label_column].map(_display_label)
    values = source[value_column].map(_finite_number)
    valid = values.notna()
    if not bool(valid.any()):
        return None

    prepared = pd.DataFrame(
        {
            "label": labels.loc[valid].tolist(),
            "value": values.loc[valid].astype(float).tolist(),
        }
    )
    selected_order = order or {}
    prepared["_rank"] = prepared["label"].map(
        lambda value: _sort_rank(value, selected_order)
    )
    prepared["_text"] = prepared["label"].astype(str)
    # Position is retained as a final key so equal labels remain stable.
    prepared["_position"] = range(len(prepared))
    return prepared.sort_values(
        ["_rank", "_text", "_position"], kind="stable"
    ).reset_index(drop=True)


def _prepare_cost(frame: pd.DataFrame) -> pd.DataFrame | None:
    """Prepare the already-grouped cost rows without creating new aggregates."""

    source = _with_column(_require_frame(frame, "cost_summary"), "category")
    if source is None:
        return None
    required = ("category", "material", "unit", "total_cost")
    if any(column not in source.columns for column in required):
        return None

    records: list[dict[str, Any]] = []
    for position, row in source.loc[:, required].iterrows():
        value = _finite_number(row["total_cost"])
        if value is None:
            continue
        category = _display_label(row["category"])
        material = _display_label(row["material"])
        unit = _display_label(row["unit"])
        records.append(
            {
                "label": f"{category} / {material} / {unit}",
                "value": value,
                "category": category,
                "material": material,
                "unit": unit,
                "_category_rank": _sort_rank(category, _CATEGORY_ORDER),
                "_material_rank": _sort_rank(material, _MATERIAL_ORDER),
                "_position": position,
            }
        )
    if not records:
        return None
    return pd.DataFrame(records).sort_values(
        [
            "_category_rank",
            "category",
            "_material_rank",
            "material",
            "unit",
            "_position",
        ],
        kind="stable",
    ).reset_index(drop=True)


def _prepare_validation(frame: pd.DataFrame) -> pd.DataFrame | None:
    """Prepare validation summary metrics for a grouped error chart."""

    source = _with_column(_require_frame(frame, "validation.summary_by_category"), "category")
    required = (
        "category",
        "mean_absolute_error",
        "mean_relative_error_pct",
    )
    if source is None or any(column not in source.columns for column in required):
        return None

    records: list[dict[str, Any]] = []
    for position, row in source.loc[:, required].iterrows():
        absolute = _finite_number(row["mean_absolute_error"])
        relative = _finite_number(row["mean_relative_error_pct"])
        if absolute is None and relative is None:
            continue
        category = _display_label(row["category"])
        records.append(
            {
                "label": category,
                "absolute": absolute,
                "relative": relative,
                "_rank": _sort_rank(category, _CATEGORY_ORDER),
                "_position": position,
            }
        )
    if not records:
        return None
    return pd.DataFrame(records).sort_values(
        ["_rank", "label", "_position"], kind="stable"
    ).reset_index(drop=True)


def _bar_figure(
    *,
    title: str,
    xaxis_title: str,
    yaxis_title: str,
    x: Any,
    y: Any,
    name: str,
    hovertemplate: str,
    legend_title: str | None = None,
) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Bar(
                x=x,
                y=y,
                name=name,
                hovertemplate=hovertemplate,
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        legend_title_text=legend_title,
    )
    return figure


def fig_elements_by_level(by_level: pd.DataFrame) -> go.Figure:
    """Show precomputed element counts for each level."""

    title = "各楼层构件数量"
    prepared = _prepare_metric(
        by_level,
        label_column="level",
        value_column="element_count",
        argument_name="by_level",
        order=_LEVEL_ORDER,
    )
    if prepared is None:
        return _empty_figure(
            title,
            xaxis_title="楼层",
            yaxis_title="构件数量（个）",
            legend_title="指标",
        )
    return _bar_figure(
        title=title,
        xaxis_title="楼层",
        yaxis_title="构件数量（个）",
        x=prepared["label"],
        y=prepared["value"],
        name="构件数量",
        hovertemplate="楼层：%{x}<br>构件数量：%{y:.0f} 个<extra></extra>",
        legend_title="指标",
    )


def fig_concrete_volume_by_level(by_level: pd.DataFrame) -> go.Figure:
    """Show precomputed volume totals for each level."""

    title = "各楼层混凝土体积"
    prepared = _prepare_metric(
        by_level,
        label_column="level",
        value_column="volume_sum",
        argument_name="by_level",
        order=_LEVEL_ORDER,
    )
    if prepared is None:
        return _empty_figure(
            title,
            xaxis_title="楼层",
            yaxis_title="体积（m³）",
            legend_title="指标",
        )
    return _bar_figure(
        title=title,
        xaxis_title="楼层",
        yaxis_title="体积（m³）",
        x=prepared["label"],
        y=prepared["value"],
        name="混凝土体积",
        hovertemplate="楼层：%{x}<br>体积：%{y:.3f} m³<extra></extra>",
        legend_title="指标",
    )


def fig_quantity_share_by_category(by_category: pd.DataFrame) -> go.Figure:
    """Show each category's precomputed quantity as a share of the whole."""

    title = "各构件类型工程量占比"
    prepared = _prepare_metric(
        by_category,
        label_column="category",
        value_column="quantity_sum",
        argument_name="by_category",
        order=_CATEGORY_ORDER,
    )
    if prepared is None:
        return _empty_figure(title, legend_title="构件类型")

    figure = go.Figure(
        data=[
            go.Pie(
                labels=prepared["label"],
                values=prepared["value"],
                name="工程量",
                textinfo="percent",
                hovertemplate=(
                    "构件类型：%{label}<br>工程量：%{value:.3f}<br>占比：%{percent}"
                    "<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        legend_title_text="构件类型",
    )
    return figure


def fig_material_usage(by_material: pd.DataFrame) -> go.Figure:
    """Compare precomputed quantities by material."""

    title = "材料用量对比"
    prepared = _prepare_metric(
        by_material,
        label_column="material",
        value_column="quantity_sum",
        argument_name="by_material",
        order=_MATERIAL_ORDER,
    )
    if prepared is None:
        return _empty_figure(
            title,
            xaxis_title="材料",
            yaxis_title="工程量（汇总单位）",
            legend_title="指标",
        )
    return _bar_figure(
        title=title,
        xaxis_title="材料",
        yaxis_title="工程量（汇总单位）",
        x=prepared["label"],
        y=prepared["value"],
        name="工程量",
        hovertemplate="材料：%{x}<br>工程量：%{y:.3f}<extra></extra>",
        legend_title="指标",
    )


def fig_cost_distribution(cost_summary: pd.DataFrame) -> go.Figure:
    """Show each precomputed category/material/unit cost row."""

    title = "示例费用分布"
    prepared = _prepare_cost(cost_summary)
    if prepared is None:
        return _empty_figure(
            title,
            xaxis_title="类别 / 材料 / 单位",
            yaxis_title="费用（元）",
            legend_title="费用指标",
        )
    customdata = prepared[["category", "material", "unit"]].to_numpy()
    return _bar_figure(
        title=title,
        xaxis_title="类别 / 材料 / 单位",
        yaxis_title="费用（元）",
        x=prepared["label"],
        y=prepared["value"],
        name="示例费用",
        hovertemplate=(
            "类别：%{customdata[0]}<br>材料：%{customdata[1]}<br>单位：%{customdata[2]}<br>"
            "费用：%{y:,.2f} 元<extra></extra>"
        ).replace("%{customdata", "%{customdata"),
        legend_title="费用指标",
    ).update_traces(customdata=customdata)


def fig_quality_issue_counts(report: QualityReport) -> go.Figure:
    """Show quality findings by rule using the report's existing counts."""

    if not isinstance(report, QualityReport):
        raise TypeError("report 必须是 QualityReport。")
    title = "数据质量问题数量"
    records: list[tuple[str, float, int]] = []
    for position, (rule, count) in enumerate(report.counts_by_rule.items()):
        number = _finite_number(count)
        if number is None:
            continue
        records.append((_display_label(rule), number, position))
    if not records:
        return _empty_figure(
            title,
            xaxis_title="质量规则",
            yaxis_title="问题数量（条）",
            legend_title="问题数量",
        )
    records.sort(key=lambda item: (item[0], item[2]))
    labels = [item[0] for item in records]
    values = [item[1] for item in records]
    return _bar_figure(
        title=title,
        xaxis_title="质量规则",
        yaxis_title="问题数量（条）",
        x=labels,
        y=values,
        name="问题数量",
        hovertemplate="质量规则：%{x}<br>问题数量：%{y:.0f} 条<extra></extra>",
        legend_title="问题数量",
    )


def fig_validation_error(validation: ValidationResult) -> go.Figure:
    """Show precomputed mean absolute and relative review errors by category."""

    if not isinstance(validation, ValidationResult):
        raise TypeError("validation 必须是 ValidationResult。")
    title = "人工复核误差"
    prepared = _prepare_validation(validation.summary_by_category)
    if prepared is None:
        return _empty_figure(
            title,
            xaxis_title="构件类别",
            yaxis_title="误差",
            legend_title="误差指标",
        )

    figure = go.Figure(
        data=[
            go.Bar(
                x=prepared["label"],
                y=prepared["absolute"],
                name="平均绝对误差",
                hovertemplate="构件类别：%{x}<br>平均绝对误差：%{y:.3f}<extra></extra>",
            ),
            go.Bar(
                x=prepared["label"],
                y=prepared["relative"],
                name="平均相对误差（%）",
                yaxis="y2",
                hovertemplate="构件类别：%{x}<br>平均相对误差：%{y:.3f}%<extra></extra>",
            ),
        ]
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        barmode="group",
        xaxis_title="构件类别",
        yaxis_title="绝对误差",
        yaxis2={
            "title": "相对误差（%）",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        legend_title_text="误差指标",
    )
    return figure


__all__ = [
    "fig_concrete_volume_by_level",
    "fig_cost_distribution",
    "fig_elements_by_level",
    "fig_material_usage",
    "fig_quality_issue_counts",
    "fig_quantity_share_by_category",
    "fig_validation_error",
]
