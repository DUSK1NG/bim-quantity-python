"""数据质量检查 Streamlit page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.app_pages._common import filter_issues
from app.utils.charts import fig_quality_issue_counts
from src.quality_report import DISCLAIMER, quality_report_to_dict


_ISSUE_COLUMNS = (
    "raw_row_number",
    "rule_id",
    "severity",
    "field",
    "message",
    "source_file",
    "guid",
    "element_name",
    "type_name",
    "level",
    "suggestion",
)


def _issues_frame(report, source_file: str) -> pd.DataFrame:
    payload = quality_report_to_dict(report, source_file)
    return pd.DataFrame(payload.get("issues", []), columns=_ISSUE_COLUMNS)


st.title("数据质量检查")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先选择 CSV 或 IFC 并完成数据处理，再查看质量规则结果。")
    st.warning("当前支持 CSV 和可选 IFC；请选择输入类型并完成加载后检查质量。")
    st.caption(DISCLAIMER)
else:
    report = artifacts.quality_report
    issues = _issues_frame(report, artifacts.source_file)
    severity_options = sorted(issues["severity"].dropna().astype(str).unique().tolist())
    rule_options = sorted(issues["rule_id"].dropna().astype(str).unique().tolist())
    severities = st.sidebar.multiselect("严重度", severity_options)
    rules = st.sidebar.multiselect("质量规则", rule_options)
    filtered = filter_issues(issues, severities=severities, rules=rules)

    columns = st.columns(3)
    columns[0].metric("检查行数", report.total_rows)
    columns[1].metric("问题行数", report.issue_rows)
    columns[2].metric("清洁行数", report.clean_rows)
    st.plotly_chart(fig_quality_issue_counts(report))
    st.subheader("质量问题明细")
    st.dataframe(filtered, hide_index=True)
    if report.not_applicable_rules:
        st.info("当前配置暂不适用的规则：" + "、".join(report.not_applicable_rules))
    st.caption(artifacts.disclaimer or DISCLAIMER)
