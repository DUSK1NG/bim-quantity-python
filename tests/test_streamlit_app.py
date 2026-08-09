"""Static and helper contracts for the six Streamlit dashboard pages."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd


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
