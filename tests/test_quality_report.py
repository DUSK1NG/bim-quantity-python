"""Contract tests for the stage 3.1 quality report."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.quality_report import (
    QualityIssue,
    QualityReport,
    quality_report_to_dict,
    write_quality_report,
)


def _report(*issues: QualityIssue, total_rows: int = 4) -> QualityReport:
    """Build a report fixture with deliberately unsorted mappings and issues."""

    return QualityReport(
        total_rows=total_rows,
        issue_rows=len({issue.raw_row_number for issue in issues}),
        clean_rows=total_rows - len({issue.raw_row_number for issue in issues}),
        counts_by_rule={"unknown_unit": 1, "missing_level": 2},
        counts_by_severity={"Error": 1, "Warning": 2},
        not_applicable_rules=("outlier_dimension", "missing_section_size"),
        issues=tuple(issues),
    )


def test_quality_issue_keeps_old_five_argument_constructor_and_accepts_trace_fields() -> None:
    legacy = QualityIssue(1, "missing_level", "Warning", "level", "缺失楼层")
    assert legacy.source_file is None
    assert legacy.guid is None
    assert legacy.element_name is None
    assert legacy.type_name is None
    assert legacy.level is None
    assert legacy.suggestion is None

    issue = QualityIssue(
        7,
        "missing_level",
        "Warning",
        "level",
        "缺失楼层；建议补充标准楼层",
        source_file=r"C:\imports\trace.csv",
        guid="GUID-7",
        element_name="梁-AA-007",
        type_name="Beam-Standard",
        level=None,
        suggestion="建议补充标准楼层",
    )
    payload = quality_report_to_dict(_report(issue), r"C:\reports\report.json")

    serialized = payload["issues"][0]
    assert serialized["source_file"] == "trace.csv"
    assert serialized["guid"] == "GUID-7"
    assert serialized["element_name"] == "梁-AA-007"
    assert serialized["type_name"] == "Beam-Standard"
    assert serialized["level"] is None
    assert serialized["suggestion"] == "建议补充标准楼层"


def test_quality_report_serializes_not_applicable_rules_in_contract_order() -> None:
    payload = quality_report_to_dict(_report(), "report.json")

    assert payload["not_applicable_rules"] == [
        "missing_section_size",
        "outlier_dimension",
    ]


def test_quality_report_serializes_stable_counts_and_disclaimer(tmp_path: Path) -> None:
    issues = (
        QualityIssue(2, "missing_level", "Warning", "level", "缺失楼层"),
        QualityIssue(2, "missing_level", "Warning", "type_name", "缺失类型"),
        QualityIssue(1, "unknown_unit", "Error", "unit", "未知单位"),
    )
    report = _report(*issues)

    output = tmp_path / "report.json"
    write_quality_report(report, output, str(tmp_path / "source" / "sample_elements.csv"))
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["total_rows"] == 4
    assert payload["issue_rows"] == 2
    assert payload["clean_rows"] == 2
    assert list(payload["counts_by_rule"]) == ["missing_level", "unknown_unit"]
    assert payload["counts_by_rule"] == {"missing_level": 2, "unknown_unit": 1}
    assert list(payload["counts_by_severity"]) == ["Error", "Warning"]
    assert payload["counts_by_severity"] == {"Error": 1, "Warning": 2}
    assert payload["not_applicable_rules"] == ["missing_section_size", "outlier_dimension"]
    assert payload["disclaimer"] == "本项目单价为教学示例数据，不用于正式工程造价。"


def test_quality_report_sorts_issues_by_row_rule_and_field() -> None:
    issues = (
        QualityIssue(2, "missing_level", "Warning", "type_name", "缺失类型"),
        QualityIssue(1, "unknown_unit", "Error", "unit", "未知单位"),
        QualityIssue(2, "duplicate_guid", "Error", "guid", "重复 GUID"),
        QualityIssue(2, "missing_level", "Warning", "level", "缺失楼层"),
    )

    serialized = quality_report_to_dict(_report(*issues), "sample_elements.csv")

    assert [
        (issue["raw_row_number"], issue["rule_id"], issue["field"])
        for issue in serialized["issues"]
    ] == [
        (1, "unknown_unit", "unit"),
        (2, "duplicate_guid", "guid"),
        (2, "missing_level", "level"),
        (2, "missing_level", "type_name"),
    ]


def test_quality_report_json_is_utf8_and_stable_with_trailing_newline(tmp_path: Path) -> None:
    report = _report(QualityIssue(1, "missing_level", "Warning", "level", "缺失楼层"))
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_quality_report(report, first, "sample_elements.csv")
    write_quality_report(report, second, "sample_elements.csv")

    first_bytes = first.read_bytes()
    assert first_bytes == second.read_bytes()
    assert first_bytes.endswith(b"\n")
    assert "缺失楼层" in first_bytes.decode("utf-8")
    assert "\\u7f3a" not in first_bytes.decode("ascii", errors="ignore")


def test_source_file_is_reduced_to_basename_without_absolute_path(tmp_path: Path) -> None:
    report = _report()
    source = tmp_path / "nested" / "sample_elements.csv"

    payload = quality_report_to_dict(report, str(source))

    assert payload["source_file"] == "sample_elements.csv"
    assert not Path(payload["source_file"]).is_absolute()
    assert "/" not in payload["source_file"]
    assert "\\" not in payload["source_file"]


def test_quality_report_dataclasses_are_frozen() -> None:
    issue = QualityIssue(1, "missing_level", "Warning", "level", "缺失楼层")
    report = _report(issue)

    with pytest.raises(FrozenInstanceError):
        issue.message = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.total_rows = 99  # type: ignore[misc]
