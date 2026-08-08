"""Contract tests for the stage 3.2 fourteen-rule quality checker.

The fixtures intentionally use the standard, cleaned field names.  Mapping and
normalisation are covered by ``data_cleaner``; the checker consumes that
contract and must retain the supplied ``raw_row_number`` values.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.config_loader import QUALITY_RULE_IDS, load_project_config
from src.schema import STANDARD_COLUMNS


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"


def _checker_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.quality_checker")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"quality checker module is not available yet: {exc}")


@pytest.fixture()
def config():
    return load_project_config(CONFIG_DIR)


def _valid_row(raw_row_number: int) -> dict[str, object]:
    """Return one complete cleaned row that does not trigger any rule."""

    return {
        "element_id": f"E-{raw_row_number}",
        "guid": f"GUID-{raw_row_number}",
        "source": "CSV",
        "ifc_class": "IfcBeam",
        "category": "Beam",
        "element_name": "梁-AA-001",
        "type_name": "Beam-Standard",
        "level": "一层",
        "material": "混凝土",
        "length_m": 1.0,
        "area_m2": 1.0,
        "volume_m3": 1.0,
        "quantity": 1.0,
        "unit": "m³",
        "unit_price": 520.0,
        "total_cost": 520.0,
        "quantity_source": "CSV Schedule",
        "quality_status": "Pass",
        "raw_unit": "m³",
        "raw_row_number": raw_row_number,
        "source_file": "quality.csv",
        "exception_tags": "",
    }


def _rule_fixture() -> pd.DataFrame:
    """Build independent rows for all applicable configured rule IDs."""

    rows = [_valid_row(index) for index in range(101, 116)]
    rows[0]["element_name"] = pd.NA
    rows[0]["material"] = pd.NA
    rows[0]["quantity"] = -1
    rows[1]["type_name"] = "  "
    rows[2]["material"] = pd.NA
    rows[3]["level"] = pd.NA
    rows[4]["guid"] = pd.NA
    rows[5]["element_id"] = "E-DUP"
    rows[6]["element_id"] = "E-DUP"
    rows[7]["quantity"] = 0
    rows[8]["quantity"] = -1
    rows[9]["unit"] = "yard"
    rows[10]["element_name"] = "INVALID"
    rows[11]["guid"] = "GUID-DUP"
    rows[12]["guid"] = "GUID-DUP"
    rows[13]["material"] = "未知材料"
    rows[13]["unit_price"] = pd.NA
    rows[13]["total_cost"] = pd.NA
    rows[14]["element_name"] = "  "
    return pd.DataFrame(rows, columns=[*STANDARD_COLUMNS, "raw_unit", "raw_row_number", "source_file", "exception_tags"])


def test_checker_emits_configured_rules_with_traceable_messages(config):
    checker = _checker_module()
    frame = _rule_fixture()
    result = checker.check_quality(frame, config)

    # The two dimension rules have no stage-3.2 configuration and therefore
    # are reported explicitly rather than fabricated as row-level issues.
    expected_applicable = set(QUALITY_RULE_IDS) - {
        "missing_section_size",
        "outlier_dimension",
    }
    assert set(result.counts_by_rule) == expected_applicable
    assert result.not_applicable_rules == (
        "missing_section_size",
        "outlier_dimension",
    )

    severity_by_id = {
        rule["id"]: rule["severity"] for rule in config.quality_rules["rules"]
    }
    assert result.issues
    for issue in result.issues:
        assert issue.rule_id in expected_applicable
        assert issue.severity == severity_by_id[issue.rule_id]
        assert issue.raw_row_number in set(frame["raw_row_number"])
        assert issue.field in frame.columns
        assert any(char >= "\u4e00" and char <= "\u9fff" for char in issue.message)
        assert "建议" in issue.message

    # Every applicable ID appears at least once, while not-applicable rules do
    # not leak into either issue rows or rule counts.
    assert expected_applicable == {issue.rule_id for issue in result.issues}
    assert "missing_section_size" not in result.counts_by_rule
    assert "outlier_dimension" not in result.counts_by_rule


def test_checker_groups_only_nonempty_duplicate_ids_and_guids(config):
    checker = _checker_module()
    rows = [_valid_row(201), _valid_row(202), _valid_row(203)]
    rows[0]["element_id"] = rows[1]["element_id"] = "E-SAME"
    rows[0]["guid"] = rows[1]["guid"] = "G-SAME"
    rows[2]["element_id"] = ""
    rows[2]["guid"] = "   "
    result = checker.check_quality(pd.DataFrame(rows), config)

    duplicate_ids = [issue for issue in result.issues if issue.rule_id == "duplicate_element_id"]
    duplicate_guids = [issue for issue in result.issues if issue.rule_id == "duplicate_guid"]
    assert {issue.raw_row_number for issue in duplicate_ids} == {201, 202}
    assert {issue.raw_row_number for issue in duplicate_guids} == {201, 202}
    assert all(issue.raw_row_number != 203 for issue in [*duplicate_ids, *duplicate_guids])


def test_checker_keeps_all_rows_and_aggregates_severity_by_rule(config):
    checker = _checker_module()
    frame = _rule_fixture()
    original = frame.copy(deep=True)
    result = checker.check_quality(frame, config)

    assert result.total_rows == len(frame)
    assert result.issue_rows == len({issue.raw_row_number for issue in result.issues})
    assert result.clean_rows == result.total_rows - result.issue_rows
    assert frame.equals(original)

    # A row can have a Warning and an Error simultaneously; the row's quality
    # state is therefore the highest configured severity (Error), not the
    # first finding encountered.
    row_101 = [issue for issue in result.issues if issue.raw_row_number == 101]
    rank = {"Info": 1, "Warning": 2, "Error": 3}
    assert max((rank[issue.severity] for issue in row_101), default=0) == rank["Error"]
    assert result.counts_by_severity == {
        "Error": sum(issue.severity == "Error" for issue in result.issues),
        "Warning": sum(issue.severity == "Warning" for issue in result.issues),
    }


def test_checker_issue_sort_is_stable_by_raw_row_rule_and_field(config):
    checker = _checker_module()
    frame = _rule_fixture().sample(frac=1.0, random_state=7).reset_index(drop=True)
    result = checker.check_quality(frame, config)

    keys = [(issue.raw_row_number, issue.rule_id, issue.field) for issue in result.issues]
    assert keys == sorted(keys)
