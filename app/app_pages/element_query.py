"""构件组合查询 Streamlit page."""

from __future__ import annotations

import streamlit as st

from app.app_pages._common import filter_elements
from src.quality_report import DISCLAIMER


def _options(frame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = {str(value).strip() for value in frame[column].dropna() if str(value).strip()}
    return sorted(values)


st.title("构件查询")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先选择 CSV 或 IFC 并完成数据处理，再使用构件查询。")
    st.warning("当前支持 CSV 和可选 IFC；请选择输入类型并完成加载后查询构件。")
    st.caption(DISCLAIMER)
else:
    elements = artifacts.standard_frame
    query = st.sidebar.text_input("名称、ID、GUID 或 IFC 类别", value="")
    category = st.sidebar.selectbox("构件类型", ["全部", *_options(elements, "category")])
    level = st.sidebar.selectbox("楼层", ["全部", *_options(elements, "level")])
    material = st.sidebar.selectbox("材料", ["全部", *_options(elements, "material")])
    filtered = filter_elements(
        elements,
        query=query,
        category=category,
        level=level,
        material=material,
    )

    st.metric("匹配构件数", len(filtered))
    if filtered.empty:
        st.info("没有符合当前条件的构件，请调整筛选条件。")
    st.dataframe(filtered, hide_index=True)
    st.caption(artifacts.disclaimer or DISCLAIMER)
