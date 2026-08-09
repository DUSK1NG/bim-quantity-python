"""项目概览 Streamlit page."""

from __future__ import annotations

import streamlit as st

from app.utils.charts import fig_elements_by_level
from src.quality_report import DISCLAIMER


st.title("项目概览")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先在应用入口上传 CSV 并完成数据处理，然后返回本页查看项目概览。")
    st.warning("当前版本仅支持 CSV 数据；IFC 直接读取暂不可用，请先导出构件明细 CSV。")
    st.caption(DISCLAIMER)
else:
    overview = dict(artifacts.overview or {})
    st.caption(f"来源文件：{overview.get('source_file', artifacts.source_file)}")

    metric_columns = st.columns(4)
    metric_columns[0].metric("构件行数", overview.get("total_rows", 0))
    metric_columns[1].metric("可信构件数", overview.get("element_count", 0))
    metric_columns[2].metric("类别数", overview.get("category_count", 0))
    metric_columns[3].metric("楼层数", overview.get("level_count", 0))

    detail_columns = st.columns(4)
    detail_columns[0].metric("总面积（m²）", overview.get("area_sum", "—"))
    detail_columns[1].metric("总体积（m³）", overview.get("volume_sum", "—"))
    detail_columns[2].metric("问题行数", overview.get("issue_rows", 0))
    detail_columns[3].metric("示例总价（元）", overview.get("total_cost", "—"))

    st.subheader("楼层构件分布")
    st.plotly_chart(fig_elements_by_level(artifacts.by_level))
    st.subheader("分楼层汇总")
    st.dataframe(artifacts.by_level, hide_index=True)
    st.caption(artifacts.disclaimer or DISCLAIMER)
