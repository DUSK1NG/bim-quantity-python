"""Contract tests for the stage 3.2 quantity calculator."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.config_loader import load_project_config


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"


def _calculator_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.quantity_calculator")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"quantity calculator module is not available yet: {exc}")


@pytest.fixture()
def config():
    return load_project_config(CONFIG_DIR)


def test_valid_existing_quantities_keep_their_source_and_value(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Column"],
            "quantity": [2.5, 3.0],
            "unit": ["m³", "m³"],
            "quantity_source": [pd.NA, "IFC BaseQuantity"],
            "length_m": [9.0, 9.0],
            "volume_m3": [8.0, 8.0],
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result.loc[0, "quantity"] == pytest.approx(2.5)
    assert result.loc[0, "quantity_source"] == "CSV Schedule"
    assert result.loc[1, "quantity"] == pytest.approx(3.0)
    assert result.loc[1, "quantity_source"] == "IFC BaseQuantity"


def test_beam_length_and_solid_volume_categories_use_parameter_calculation(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Column", "Slab", "Wall"],
            "quantity": [float("nan"), pd.NA, pd.NA, pd.NA],
            "unit": [pd.NA] * 4,
            "quantity_source": [pd.NA] * 4,
            "length_m": [4.5, pd.NA, pd.NA, pd.NA],
            "volume_m3": [pd.NA, 1.25, 2.5, 3.75],
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result["quantity"].tolist() == pytest.approx([4.5, 1.25, 2.5, 3.75])
    assert result["unit"].tolist() == ["m", "m³", "m³", "m³"]
    assert result["quantity_source"].tolist() == [
        "Parameter Calculation",
        "Parameter Calculation",
        "Parameter Calculation",
        "Parameter Calculation",
    ]


def test_door_and_window_use_available_count_with_piece_unit(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Door", "Window"],
            "quantity": [2.0, 3.0],
            "unit": [pd.NA, "m³"],
            "quantity_source": [pd.NA, pd.NA],
            "length_m": [2.0, 2.0],
            "volume_m3": [1.0, 1.0],
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result["quantity"].tolist() == [2.0, 3.0]
    assert result["unit"].tolist() == ["樘", "樘"]
    assert result["quantity_source"].tolist() == ["CSV Schedule", "CSV Schedule"]


def test_missing_dimensions_leave_quantity_and_unit_missing(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Column", "Door", "Window", "Furniture"],
            "quantity": [pd.NA] * 5,
            "unit": [pd.NA] * 5,
            "quantity_source": [pd.NA] * 5,
            "length_m": [pd.NA] * 5,
            "volume_m3": [pd.NA] * 5,
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result["quantity"].isna().all()
    assert result["unit"].isna().all()
    assert result["quantity_source"].tolist() == ["Missing"] * 5


def test_negative_dimensions_do_not_trigger_a_fallback_calculation(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Column", "Slab", "Wall"],
            "quantity": [pd.NA] * 4,
            "unit": [pd.NA] * 4,
            "quantity_source": [pd.NA] * 4,
            "length_m": [-4.5, pd.NA, pd.NA, pd.NA],
            "volume_m3": [pd.NA, -1.25, -2.5, -3.75],
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result["quantity"].isna().all()
    assert result["unit"].isna().all()
    assert result["quantity_source"].tolist() == ["Missing"] * 4


def test_negative_existing_quantity_is_not_replaced_by_dimensions(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "quantity": [-2.0],
            "unit": ["m³"],
            "quantity_source": ["CSV Schedule"],
            "length_m": [4.5],
            "volume_m3": [1.0],
        }
    )

    result = calculator.calculate_quantities(frame, config).frame

    assert result.loc[0, "quantity"] == pytest.approx(-2.0)
    assert result.loc[0, "quantity_source"] == "Missing"


def test_calculation_does_not_mutate_input_dataframe(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "quantity": [pd.NA],
            "unit": [pd.NA],
            "quantity_source": [pd.NA],
            "length_m": [4.5],
            "volume_m3": [pd.NA],
        }
    )
    original = frame.copy(deep=True)

    result = calculator.calculate_quantities(frame, config)

    pd.testing.assert_frame_equal(frame, original)
    assert result.frame is not frame
    assert result.calculation_notes
    assert isinstance(result.calculation_notes, tuple)
