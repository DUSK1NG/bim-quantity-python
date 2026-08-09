"""Contract tests for stage 3.2 manual quantity validation.

The tests describe the public validation contract before the implementation is
added.  They intentionally use small, fully traceable DataFrames so every
association and error can be inspected without relying on a UI or an export
layer.
"""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).parents[1]


def _validation_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.validation")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"validation module is not available yet: {exc}")


def _calculated_frame(*rows: dict[str, object]) -> pd.DataFrame:
    """Build sparse-but-standard calculated rows for focused contract tests."""

    defaults = {
        "element_id": "E-1",
        "guid": "GUID-1",
        "ifc_class": "IfcBeam",
        "category": "Beam",
        "level": "一层",
        "quantity": 2.0,
        "raw_row_number": 11,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_sample_manual_csv_validates_by_guid_without_overwriting_calculated_values():
    validation = _validation_module()
    calculated = pd.read_csv(ROOT / "data" / "sample" / "sample_elements.csv")
    manual = pd.read_csv(ROOT / "data" / "sample" / "sample_manual_validation.csv")
    manual.loc[0, "auto_quantity"] = 999.0

    result = validation.validate_manual_results(calculated, manual)

    assert len(result.details) == len(manual)
    assert result.details["guid"].tolist() == manual["guid"].tolist()
    assert result.details.loc[0, "auto_quantity"] == pytest.approx(2.089)
    assert result.details.loc[0, "manual_quantity"] == pytest.approx(2.09)
    assert result.details.loc[0, "absolute_error"] == pytest.approx(0.001)
    assert result.details.loc[0, "relative_error_pct"] == pytest.approx(0.001 / 2.09 * 100)
    # The manual CSV's optional auto_quantity column must not replace the
    # calculated quantity used in the comparison.
    assert result.details["auto_quantity"].tolist() != manual["auto_quantity"].tolist()


def test_association_falls_back_from_guid_to_element_id_then_raw_row_number():
    validation = _validation_module()
    calculated = _calculated_frame(
        {"element_id": "E-ID", "guid": pd.NA, "raw_row_number": 21, "quantity": 3.0},
        {"element_id": "E-ROW", "guid": pd.NA, "raw_row_number": 22, "quantity": 4.0},
        {"element_id": "E-GUID", "guid": "G-3", "raw_row_number": 23, "quantity": 5.0},
    )
    manual = pd.DataFrame(
        [
            {"guid": pd.NA, "element_id": "E-ID", "manual_quantity": 3.5},
            {"guid": "", "element_id": pd.NA, "raw_row_number": 22, "manual_quantity": 4.5},
            {"guid": "G-3", "element_id": "E-GUID", "manual_quantity": 5.5},
        ]
    )

    result = validation.validate_manual_results(calculated, manual)

    assert result.details["match_key_type"].tolist() == [
        "element_id",
        "raw_row_number",
        "guid",
    ]
    assert result.details["auto_quantity"].tolist() == pytest.approx([3.0, 4.0, 5.0])


def test_errors_use_manual_denominator_and_zero_manual_value_is_missing_relative_error():
    validation = _validation_module()
    calculated = _calculated_frame(
        {"guid": "G-1", "raw_row_number": 31, "quantity": 2.0},
        {"guid": "G-2", "raw_row_number": 32, "quantity": 0.0},
    )
    manual = pd.DataFrame(
        [
            {"guid": "G-1", "manual_quantity": 1.0},
            {"guid": "G-2", "manual_quantity": 0.0},
        ]
    )

    result = validation.validate_manual_results(calculated, manual)

    assert result.details.loc[0, "absolute_error"] == pytest.approx(1.0)
    assert result.details.loc[0, "relative_error_pct"] == pytest.approx(100.0)
    assert result.details.loc[1, "absolute_error"] == pytest.approx(0.0)
    assert pd.isna(result.details.loc[1, "relative_error_pct"])
    assert any("人工值为零" in message for message in result.messages)
    assert any("人工值为零" in str(message) for message in result.details["message"])


def test_duplicate_manual_key_is_rejected_before_association():
    validation = _validation_module()
    calculated = _calculated_frame({"guid": "G-DUP", "raw_row_number": 41})
    manual = pd.DataFrame(
        [
            {"guid": "G-DUP", "manual_quantity": 1.0, "raw_row_number": 101},
            {"guid": "G-DUP", "manual_quantity": 1.1, "raw_row_number": 102},
        ]
    )

    with pytest.raises(validation.ValidationError, match="重复人工键") as exc_info:
        validation.validate_manual_results(calculated, manual)

    assert "101" in str(exc_info.value)
    assert "102" in str(exc_info.value)


def test_missing_and_unmatched_keys_are_rejected_with_traceable_row_numbers():
    validation = _validation_module()
    calculated = _calculated_frame({"guid": "G-OK", "raw_row_number": 51})

    no_key = pd.DataFrame([{"guid": "", "element_id": pd.NA, "manual_quantity": 1.0}])
    with pytest.raises(validation.ValidationError, match="匹配键") as exc_info:
        validation.validate_manual_results(calculated, no_key)
    assert "第 1 行" in str(exc_info.value)

    unmatched = pd.DataFrame([{"guid": "G-MISSING", "manual_quantity": 1.0, "raw_row_number": 77}])
    with pytest.raises(validation.ValidationError, match="无法匹配") as exc_info:
        validation.validate_manual_results(calculated, unmatched)
    assert "77" in str(exc_info.value)


@pytest.mark.parametrize("manual_value", ["not-a-number", float("inf"), -1.0])
def test_illegal_manual_quantity_is_rejected_with_row_number(manual_value):
    validation = _validation_module()
    calculated = _calculated_frame({"guid": "G-BAD", "raw_row_number": 61})
    manual = pd.DataFrame(
        [{"guid": "G-BAD", "manual_quantity": manual_value, "raw_row_number": 88}]
    )

    with pytest.raises(validation.ValidationError, match="manual_quantity") as exc_info:
        validation.validate_manual_results(calculated, manual)
    assert "88" in str(exc_info.value)


def test_summary_by_category_contains_mean_and_max_errors():
    validation = _validation_module()
    calculated = _calculated_frame(
        {"guid": "G-A1", "category": "Beam", "quantity": 2.0, "raw_row_number": 71},
        {"guid": "G-A2", "category": "Beam", "quantity": 4.0, "raw_row_number": 72},
        {"guid": "G-B1", "category": "Door", "quantity": 1.0, "raw_row_number": 73},
    )
    manual = pd.DataFrame(
        [
            {"guid": "G-A1", "manual_quantity": 1.0},
            {"guid": "G-A2", "manual_quantity": 2.0},
            {"guid": "G-B1", "manual_quantity": 2.0},
        ]
    )

    result = validation.validate_manual_results(calculated, manual)

    summary = result.summary_by_category.set_index("category")
    assert set(summary.index) == {"Beam", "Door"}
    assert summary.loc["Beam", "count"] == 2
    assert summary.loc["Beam", "mean_absolute_error"] == pytest.approx(1.5)
    assert summary.loc["Beam", "max_absolute_error"] == pytest.approx(2.0)
    assert summary.loc["Beam", "mean_relative_error_pct"] == pytest.approx(100.0)
    assert summary.loc["Door", "max_relative_error_pct"] == pytest.approx(50.0)


def test_result_is_frozen_and_inputs_are_not_mutated():
    validation = _validation_module()
    calculated = _calculated_frame({"guid": "G-KEEP", "raw_row_number": 81})
    manual = pd.DataFrame([{"guid": "G-KEEP", "manual_quantity": 1.5}])
    original_calculated = calculated.copy(deep=True)
    original_manual = manual.copy(deep=True)

    result = validation.validate_manual_results(calculated, manual)

    pd.testing.assert_frame_equal(calculated, original_calculated)
    pd.testing.assert_frame_equal(manual, original_manual)
    assert {"auto_quantity", "manual_quantity", "absolute_error", "relative_error_pct"} <= set(
        result.details.columns
    )
    with pytest.raises(FrozenInstanceError):
        result.messages = ("changed",)


def test_missing_required_columns_raise_validation_error():
    validation = _validation_module()
    with pytest.raises(validation.ValidationError, match="quantity"):
        validation.validate_manual_results(
            pd.DataFrame([{"guid": "G-1"}]),
            pd.DataFrame([{"guid": "G-1", "manual_quantity": 1.0}]),
        )
    with pytest.raises(validation.ValidationError, match="manual_quantity"):
        validation.validate_manual_results(
            _calculated_frame({}),
            pd.DataFrame([{"guid": "G-1"}]),
        )
