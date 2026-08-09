"""Streamlit entrypoint and shared session state for the six-page dashboard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"

_PAGE_DEFINITIONS = (
    ("app_pages/overview.py", "项目概览", ":material/dashboard:"),
    ("app_pages/quantity_analysis.py", "工程量分析", ":material/analytics:"),
    ("app_pages/element_query.py", "构件查询", ":material/search:"),
    ("app_pages/quality_check.py", "数据质量检查", ":material/verified:"),
    ("app_pages/error_analysis.py", "误差分析", ":material/compare_arrows:"),
    ("app_pages/report_export.py", "报表导出", ":material/download:"),
)


def _initialize_session_state() -> None:
    """Initialize the small set of values shared by every page."""

    defaults = {
        "uploaded_bytes": None,
        "source_name": None,
        "manual_bytes": None,
        "artifacts": None,
        "pipeline_error": None,
        "config_dir": CONFIG_DIR,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


st.set_page_config(
    page_title="BIM 工程量分析",
    page_icon=":material/architecture:",
    layout="wide",
)
_initialize_session_state()


def _render_input_panel() -> None:
    """Render the small CSV-only input panel shared by all pages."""

    with st.sidebar:
        st.subheader("数据输入")
        elements_upload = st.file_uploader(
            "构件明细 CSV",
            type=["csv"],
            key="elements-upload",
            help="当前版本读取 UTF-8 CSV；IFC reader 尚未启用。",
        )
        manual_upload = st.file_uploader(
            "人工复核 CSV（可选）",
            type=["csv"],
            key="manual-upload",
        )
        if st.button("加载数据", key="load-data"):
            if elements_upload is None:
                st.session_state["pipeline_error"] = "请先选择构件明细 CSV。"
                st.session_state["artifacts"] = None
            else:
                try:
                    from app.utils.data import DataLoadError, load_artifacts_from_bytes

                    st.session_state["artifacts"] = load_artifacts_from_bytes(
                        elements_upload.getvalue(),
                        elements_upload.name,
                        st.session_state["config_dir"],
                        manual_content=(
                            manual_upload.getvalue() if manual_upload is not None else None
                        ),
                    )
                    st.session_state["source_name"] = elements_upload.name
                    st.session_state["pipeline_error"] = None
                except DataLoadError as exc:
                    st.session_state["artifacts"] = None
                    st.session_state["pipeline_error"] = str(exc)
                except Exception as exc:  # noqa: BLE001 - UI boundary
                    st.session_state["artifacts"] = None
                    st.session_state["pipeline_error"] = (
                        f"数据加载失败：{exc}；请检查 CSV 编码和必需列后重试。"
                    )

        if st.session_state.get("pipeline_error"):
            st.error(st.session_state["pipeline_error"])
        elif st.session_state.get("artifacts") is not None:
            st.success("数据已加载，可在上方页面导航中查看结果。")


_render_input_panel()

_pages = [
    st.Page(path, title=title, icon=icon, default=index == 0)
    for index, (path, title, icon) in enumerate(_PAGE_DEFINITIONS)
]
_current_page = st.navigation(_pages, position="top")
_current_page.run()
