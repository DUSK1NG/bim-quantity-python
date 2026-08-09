"""报表导出 Streamlit page."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from src.quality_report import DISCLAIMER
from src.report_generator import write_csv_exports, write_excel_report


st.title("报表导出")
artifacts = st.session_state.get("artifacts")

if artifacts is None:
    st.info("请先上传 CSV 并完成数据处理，再生成 Excel 或 CSV 报表。")
    st.warning("当前版本仅支持 CSV 数据；IFC 直接读取暂不可用。")
    st.caption(DISCLAIMER)
else:
    source_stem = Path(artifacts.source_file).stem or "bim_quantity_report"
    st.subheader("导出预览")
    st.dataframe(artifacts.by_category, hide_index=True)
    with tempfile.TemporaryDirectory(prefix="bim-report-") as temporary_dir:
        output_dir = Path(temporary_dir)
        excel_path = output_dir / f"{source_stem}_report.xlsx"
        write_excel_report(artifacts, excel_path)
        csv_paths = write_csv_exports(artifacts, output_dir)
        excel_bytes = excel_path.read_bytes()
        csv_payloads = [(path.name, path.read_bytes()) for path in csv_paths]

    st.download_button(
        "下载 Excel 报表",
        data=excel_bytes,
        file_name=excel_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.subheader("下载 CSV 明细")
    for file_name, payload in csv_payloads:
        st.download_button(
            f"下载 {file_name}",
            data=payload,
            file_name=file_name,
            mime="text/csv",
            key=f"download-{file_name}",
        )
    st.caption("报表包含项目概览、构件明细、汇总、质量问题和人工复核结果。")
    st.caption(artifacts.disclaimer or DISCLAIMER)
