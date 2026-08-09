"""Static and helper contracts for the six Streamlit dashboard pages."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parents[1]
PAGE_NAMES = (
    "overview",
    "quantity_analysis",
    "element_query",
    "quality_check",
    "error_analysis",
    "report_export",
)


def _page_source(name: str) -> str:
    return (ROOT / "app" / "app_pages" / f"{name}.py").read_text(encoding="utf-8")


def test_all_dashboard_pages_exist_and_follow_static_contract() -> None:
    """Pages are direct Streamlit scripts and only consume prepared artifacts."""

    for name in PAGE_NAMES:
        source = _page_source(name)
        tree = ast.parse(source)
        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        )

        assert 'st.session_state.get("artifacts")' in source
        assert "use_container_width" not in source
        assert "legacy" not in source.lower()
        assert "app_pages/" not in source
        assert "calculator" not in " ".join(imports).lower()
        assert "reader" not in " ".join(imports).lower()
        assert "st.dataframe" in source or "st.plotly_chart" in source


def test_empty_quantity_filter_returns_copy_without_error() -> None:
    from app.app_pages._common import filter_summary

    frame = pd.DataFrame({"level": ["一层"], "quantity_sum": [1.0]})
    result = filter_summary(frame, levels=[], categories=[], materials=[])

    assert result.equals(frame)
    assert result is not frame


def test_empty_element_query_returns_all_rows() -> None:
    from app.app_pages._common import filter_elements

    frame = pd.DataFrame(
        {"element_name": ["梁-AA-001", "柱-AA-002"], "category": ["Beam", "Column"]}
    )
    result = filter_elements(frame, query="", category="全部", level="全部")

    assert result["element_name"].tolist() == frame["element_name"].tolist()
    assert result is not frame


def test_empty_quality_and_error_filters_are_safe() -> None:
    from app.app_pages._common import filter_issues, filter_validation

    issues = pd.DataFrame({"severity": ["Warning"], "rule_id": ["missing_level"]})
    details = pd.DataFrame({"category": ["Beam"], "absolute_error": [0.2]})

    assert filter_issues(issues, severities=[], rules=[]).equals(issues)
    assert filter_validation(details, categories=[], minimum_error=0).equals(details)


def _sample_app() -> AppTest:
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py")).run(timeout=60)
    sample_bytes = (ROOT / "data" / "sample" / "sample_elements.csv").read_bytes()
    app.file_uploader[0].upload("sample_elements.csv", sample_bytes, "text/csv").run(
        timeout=60
    )
    return app


def test_entry_shows_csv_controls_and_chinese_empty_state() -> None:
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py")).run(timeout=60)

    assert not app.exception
    assert {u.label for u in app.file_uploader} == {"构件明细 CSV", "人工复核 CSV（可选）"}
    assert any("请先" in item.value for item in app.info)
    assert any("IFC" in item.value for item in app.warning)


def test_sample_upload_loads_kpis_and_quantity_filters() -> None:
    app = _sample_app()
    app.button[0].click().run(timeout=60)

    assert not app.exception
    assert any(metric.label == "构件行数" and metric.value == "240" for metric in app.metric)

    app.switch_page("app_pages/quantity_analysis.py").run(timeout=60)
    assert not app.exception
    assert {item.label for item in app.multiselect} >= {
        "楼层筛选",
        "构件类型筛选",
        "材料筛选",
    }
    assert len(app.dataframe) >= 2


def test_report_page_exposes_excel_and_csv_downloads() -> None:
    app = _sample_app()
    app.button[0].click().run(timeout=60)
    app.switch_page("app_pages/report_export.py").run(timeout=60)

    assert not app.exception
    labels = [item.label for item in app.download_button]
    assert "下载 Excel 报表" in labels
    assert len([label for label in labels if label.endswith(".csv")]) == 6


def test_bad_upload_shows_chinese_error_without_traceback() -> None:
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py")).run(timeout=60)
    app.file_uploader[0].upload("bad.csv", b"not,a,valid\n1,2,3\n", "text/csv").run(
        timeout=60
    )
    app.button[0].click().run(timeout=60)

    assert not app.exception
    assert any("数据加载失败" in item.value for item in app.error)


def test_ifc_selector_shows_optional_upload_and_actionable_missing_dependency(
    monkeypatch,
) -> None:
    """IFC selection is visible and missing optional dependency stays user-facing."""

    from app.utils import data as data_module
    from src.ifc_reader import IfcReaderUnavailable

    def unavailable(path, config):
        raise IfcReaderUnavailable("请安装 requirements-ifc.txt")

    monkeypatch.setattr(data_module, "read_ifc", unavailable)
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py")).run(timeout=60)
    app.radio[0].set_value("IFC").run(timeout=60)

    assert not app.exception
    assert app.file_uploader[0].label == "IFC 模型"
    app.file_uploader[0].upload("model.ifc", b"not-an-ifc", "application/octet-stream").run(
        timeout=60
    )
    app.button[0].click().run(timeout=60)

    assert not app.exception
    assert any(
        "requirements-ifc" in item.value or "IFC" in item.value for item in app.error
    )
