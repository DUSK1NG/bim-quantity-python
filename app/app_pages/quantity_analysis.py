"""工程量分析 Streamlit page."""

from __future__ import annotations

import streamlit as st

from app.app_pages._common import filter_summary
from app.utils.charts import (
    fig_concrete_volume_by_level,
    fig_cost_distribution,
    fig_elements_by_level,
    fig_material_usage,
    fig_quantity_share_by_category,
)
from src.quality_report import DISCLAIMER


def _options(frame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = {str(value).strip() for value in frame[column].dropna() if str(value).strip()}
    return sorted(values)


st.title("工程量分析")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先上传 CSV 并完成数据处理，再查看工程量分析。")
    st.warning("当前版本仅支持 CSV 数据；IFC 直接读取暂不可用。")
    st.caption(DISCLAIMER)
else:
    by_level = artifacts.by_level
    by_category = artifacts.by_category
    by_material = artifacts.by_material
    cost_summary = artifacts.cost_summary

    level_options = _options(by_level, "level")
    category_options = _options(by_category, "category")
    material_options = _options(by_material, "material")
    selected_levels = st.sidebar.multiselect("楼层筛选", level_options)
    selected_categories = st.sidebar.multiselect("构件类型筛选", category_options)
    selected_materials = st.sidebar.multiselect("材料筛选", material_options)

    filtered_level = filter_summary(
        by_level,
        levels=selected_levels,
        categories=selected_categories,
        materials=selected_materials,
    )
    filtered_category = filter_summary(
        by_category,
        levels=selected_levels,
        categories=selected_categories,
        materials=selected_materials,
    )
    filtered_material = filter_summary(
        by_material,
        levels=selected_levels,
        categories=selected_categories,
        materials=selected_materials,
    )
    filtered_cost = filter_summary(
        cost_summary,
        categories=selected_categories,
        materials=selected_materials,
    )

    first, second = st.columns(2)
    with first:
        st.plotly_chart(fig_elements_by_level(filtered_level))
    with second:
        st.plotly_chart(fig_concrete_volume_by_level(filtered_level))
    first, second = st.columns(2)
    with first:
        st.plotly_chart(fig_quantity_share_by_category(filtered_category))
    with second:
        st.plotly_chart(fig_material_usage(filtered_material))
    st.plotly_chart(fig_cost_distribution(filtered_cost))

    st.subheader("筛选后的楼层汇总")
    st.dataframe(filtered_level, hide_index=True)
    st.subheader("筛选后的构件类型汇总")
    st.dataframe(filtered_category, hide_index=True)
    st.caption(artifacts.disclaimer or DISCLAIMER)
