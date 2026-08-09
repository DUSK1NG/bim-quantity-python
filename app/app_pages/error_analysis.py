"""误差分析 Streamlit page."""

from __future__ import annotations

import streamlit as st

from app.app_pages._common import filter_validation
from app.utils.charts import fig_validation_error
from src.quality_report import DISCLAIMER


def _options(frame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = {str(value).strip() for value in frame[column].dropna() if str(value).strip()}
    return sorted(values)


st.title("误差分析")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先选择 CSV 或 IFC，并可选上传人工复核表，再查看误差分析。")
    st.warning("当前支持 CSV 和可选 IFC；请选择输入类型并完成加载后查看误差。")
    st.caption(DISCLAIMER)
else:
    validation = artifacts.validation_result
    details = validation.details
    summary = validation.summary_by_category
    categories = st.sidebar.multiselect("构件类别", _options(details, "category"))
    minimum_error = st.sidebar.number_input(
        "最小绝对误差", min_value=0.0, value=0.0, step=0.001, format="%.3f"
    )
    filtered = filter_validation(
        details, categories=categories, minimum_error=minimum_error
    )

    if details.empty:
        st.info("当前没有人工复核记录；上传人工复核 CSV 后可查看误差。")
    else:
        st.plotly_chart(fig_validation_error(validation))
    st.subheader("误差汇总")
    st.dataframe(summary, hide_index=True)
    st.subheader("误差明细")
    st.dataframe(filtered, hide_index=True)
    for message in validation.messages:
        st.info(message)
    st.caption(artifacts.disclaimer or DISCLAIMER)
