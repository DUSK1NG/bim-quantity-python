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

_pages = [
    st.Page(path, title=title, icon=icon, default=index == 0)
    for index, (path, title, icon) in enumerate(_PAGE_DEFINITIONS)
]
_current_page = st.navigation(_pages, position="top")
_current_page.run()
