"""Contract tests for the stage 3.3 Excel and CSV report generator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.pipeline import PipelineArtifacts
from src.quality_report import DISCLAIMER, QualityIssue, QualityReport
from src.validation import ValidationResult


SHEETS = (
    "项目概览",
    "全部构件明细",
    "分楼层工程量",
    "分构件工程量",
    "分材料工程量",
    "示例造价汇总",
    "数据质量问题",
    "人工复核结果",
)


def _artifacts() -> PipelineArtifacts:
    standard = pd.DataFrame(
        [
            {
                "element_id": "E-1",
                "guid": "G-1",
                "source": "CSV",
                "ifc_class": "IfcBeam",
                "category": "Beam",
                "element_name": "梁-AA-001",
                "type_name": "IfcBeam-Standard",
                "level": "一层",
                "material": "混凝土",
                "length_m": 3.14159,
                "area_m2": 4.56789,
                "volume_m3": 1.23456,
                "quantity": 1.23456,
                "unit": "m³",
                "unit_price": 520.0,
                "total_cost": 641.1712,
                "quantity_source": "CSV Schedule",
                "quality_status": "Warning",
                "raw_unit": "m³",
                "raw_row_number": 2,
                "source_file": r"C:\imports\sample_elements.csv",
                "exception_tags": "missing_level",
            },
            {
                "element_id": "E-2",
                "guid": "G-2",
                "source": "CSV",
                "ifc_class": "IfcDoor",
                "category": "Door",
                "element_name": "门-AA-002",
                "type_name": "IfcDoor-Standard",
                "level": "二层",
                "material": "木材",
                "length_m": 1.0,
                "area_m2": 2.0,
                "volume_m3": 0.2,
                "quantity": 1.0,
                "unit": "樘",
                "unit_price": 860.0,
                "total_cost": 860.0,
                "quantity_source": "CSV Schedule",
                "quality_status": "Pass",
                "raw_unit": "樘",
                "raw_row_number": 3,
                "source_file": r"C:\imports\sample_elements.csv",
                "exception_tags": "",
            },
        ]
    )
    issue = QualityIssue(
        2,
        "missing_level",
        "Warning",
        "level",
        "缺失楼层",
        source_file=r"C:\imports\sample_elements.csv",
        guid="G-1",
    )
    report = QualityReport(
        total_rows=2,
        issue_rows=1,
        clean_rows=1,
        counts_by_rule={"missing_level": 1},
        counts_by_severity={"Warning": 1},
        not_applicable_rules=("missing_section_size", "outlier_dimension"),
        issues=(issue,),
    )
    validation = ValidationResult(
        details=pd.DataFrame(
            [
                {
                    "match_key_type": "guid",
                    "match_key": "G-1",
                    "element_id": "E-1",
                    "guid": "G-1",
                    "raw_row_number": 2,
                    "source_file": r"C:\imports\sample_elements.csv",
                    "ifc_class": "IfcBeam",
                    "category": "Beam",
                    "level": "一层",
                    "auto_quantity": 1.23456,
                    "manual_quantity": 1.2,
                    "absolute_error": 0.03456,
                    "relative_error_pct": 2.88,
                    "manual_row_number": 1,
                    "message": "",
                }
            ]
        ),
        summary_by_category=pd.DataFrame(),
        messages=(),
    )
    return PipelineArtifacts(
        standard_frame=standard,
        quality_report=report,
        validation_result=validation,
        overview={
            "source_file": "sample_elements.csv",
            "total_rows": 2,
            "element_count": 2,
            "category_count": 2,
            "level_count": 2,
            "area_sum": 6.56789,
            "volume_sum": 1.43456,
            "issue_rows": 1,
            "total_cost": 1501.1712,
            "disclaimer": DISCLAIMER,
        },
        by_level=pd.DataFrame(
            [{"level": "一层", "element_count": 1, "quantity_sum": 1.23456, "area_sum": 4.56789, "volume_sum": 1.23456, "total_cost": 641.1712}]
        ),
        by_category=pd.DataFrame(
            [{"category": "Beam", "element_count": 1, "quantity_sum": 1.23456, "area_sum": 4.56789, "volume_sum": 1.23456, "total_cost": 641.1712}]
        ),
        by_material=pd.DataFrame(
            [{"material": "混凝土", "element_count": 1, "quantity_sum": 1.23456, "area_sum": 4.56789, "volume_sum": 1.23456, "total_cost": 641.1712}]
        ),
        cost_summary=pd.DataFrame(
            [{"category": "Beam", "material": "混凝土", "unit": "m³", "element_count": 1, "quantity_sum": 1.23456, "area_sum": 4.56789, "volume_sum": 1.23456, "total_cost": 641.1712}]
        ),
        source_file=r"C:\imports\sample_elements.csv",
        disclaimer=DISCLAIMER,
    )


def test_excel_report_has_fixed_sheets_metadata_and_formats(tmp_path: Path) -> None:
    """Excel output is readable, traceable, and retains quality findings."""

    from src.report_generator import write_excel_report

    output = tmp_path / "nested" / "sample_report.xlsx"
    write_excel_report(_artifacts(), output)

    workbook = load_workbook(output)
    assert tuple(workbook.sheetnames) == SHEETS
    for sheet in workbook.worksheets:
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref

    overview = workbook["项目概览"]
    values = [cell.value for row in overview.iter_rows() for cell in row]
    assert "sample_elements.csv" in values
    assert DISCLAIMER in values

    details = workbook["全部构件明细"]
    assert details["J2"].number_format == "0.000"
    assert details["P2"].number_format == "0.00"
    assert details["U2"].value == "sample_elements.csv"
    quality = workbook["数据质量问题"]
    assert quality.max_row - 1 == _artifacts().quality_report.issue_rows
    assert quality["C2"].value == "Warning"


def test_csv_exports_are_utf8_sig_and_use_basename_sources(tmp_path: Path) -> None:
    """All required CSV exports are stable and never leak absolute paths."""

    from src.report_generator import write_csv_exports

    paths = write_csv_exports(_artifacts(), tmp_path / "exports")

    assert len(paths) == 6
    assert all(path.exists() for path in paths)
    decoded: dict[str, str] = {}
    for path in paths:
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        assert "C:\\imports" not in text
        decoded[path.name] = text

    assert "sample_elements.csv" in decoded["sample_elements_details.csv"]
    assert "sample_elements.csv" in decoded["sample_elements_quality_issues.csv"]
