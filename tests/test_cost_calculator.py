"""Contract tests for the stage 3.2 teaching cost calculator."""

from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pandas as pd
import pytest

from src.config_loader import load_project_config
from src.quality_report import DISCLAIMER


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"


def _calculator_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.cost_calculator")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"cost calculator module is not available yet: {exc}")


@pytest.fixture()
def config():
    return load_project_config(CONFIG_DIR)


def test_exact_category_material_unit_matches_calculates_beam_and_door(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Door"],
            "material": ["混凝土", "木材"],
            "unit": ["m³", "樘"],
            "quantity": [2.0, 3.0],
            "unit_price": [pd.NA, pd.NA],
            "total_cost": [pd.NA, pd.NA],
            "raw_row_number": [7, 8],
        }
    )

    result = calculator.calculate_costs(frame, config)

    assert result.frame["unit_price"].tolist() == pytest.approx([520.0, 860.0])
    assert result.frame["total_cost"].tolist() == pytest.approx([1040.0, 2580.0])
    assert result.unmatched_rows == ()


def test_unknown_material_unit_and_category_keep_prices_missing(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Beam", "Furniture"],
            "material": ["未知材料", "混凝土", "木材"],
            "unit": ["m³", "m3", "m³"],
            "quantity": [1.0, 1.0, 1.0],
            "raw_row_number": [21, 22, 23],
        }
    )

    result = calculator.calculate_costs(frame, config)

    assert result.frame["unit_price"].isna().all()
    assert result.frame["total_cost"].isna().all()
    assert result.unmatched_rows == (21, 22, 23)
    assert not result.frame["unit_price"].notna().any()
    assert not result.frame["total_cost"].notna().any()


@pytest.mark.parametrize("quantity", [pd.NA, float("nan"), float("inf"), -1.0, "not-a-number"])
def test_invalid_quantity_keeps_price_and_total_missing(config, quantity):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "material": ["混凝土"],
            "unit": ["m³"],
            "quantity": [quantity],
            "raw_row_number": [31],
        }
    )

    result = calculator.calculate_costs(frame, config)

    assert pd.isna(result.frame.loc[0, "unit_price"])
    assert pd.isna(result.frame.loc[0, "total_cost"])
    assert result.unmatched_rows == (31,)


def test_category_unit_fallback_requires_explicit_missing_material_record(config):
    calculator = _calculator_module()
    prices = pd.concat(
        [
            config.unit_prices,
            pd.DataFrame(
                [{"category": "Beam", "material": pd.NA, "unit": "m³", "unit_price": 410.0}]
            ),
        ],
        ignore_index=True,
    )
    fallback_config = replace(config, unit_prices=prices)
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "material": ["未知材料"],
            "unit": ["m³"],
            "quantity": [2.0],
            "raw_row_number": [41],
        }
    )

    result = calculator.calculate_costs(frame, fallback_config)

    assert result.frame.loc[0, "unit_price"] == pytest.approx(410.0)
    assert result.frame.loc[0, "total_cost"] == pytest.approx(820.0)
    assert result.unmatched_rows == ()


def test_no_fuzzy_material_match_even_when_category_and_unit_exist(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "material": ["混凝土-高强"],
            "unit": ["m³"],
            "quantity": [2.0],
            "raw_row_number": [51],
        }
    )

    result = calculator.calculate_costs(frame, config)

    assert pd.isna(result.frame.loc[0, "unit_price"])
    assert pd.isna(result.frame.loc[0, "total_cost"])
    assert result.unmatched_rows == (51,)


def test_calculation_does_not_mutate_input_and_preserves_rows(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam", "Beam"],
            "material": ["混凝土", "未知材料"],
            "unit": ["m³", "m³"],
            "quantity": [2.0, 1.0],
            "unit_price": [999.0, 888.0],
            "total_cost": [1998.0, 888.0],
            "raw_row_number": [61, 62],
            "extra": ["keep", "also-keep"],
        }
    )
    original = frame.copy(deep=True)

    result = calculator.calculate_costs(frame, config)

    pd.testing.assert_frame_equal(frame, original)
    assert result.frame is not frame
    assert len(result.frame) == len(frame)
    assert result.frame["extra"].tolist() == ["keep", "also-keep"]


def test_result_is_frozen_and_exports_shared_disclaimer_constant(config):
    calculator = _calculator_module()
    frame = pd.DataFrame(
        {
            "category": ["Beam"],
            "material": ["混凝土"],
            "unit": ["m³"],
            "quantity": [1.0],
            "raw_row_number": [71],
        }
    )

    result = calculator.calculate_costs(frame, config)

    assert calculator.DISCLAIMER == DISCLAIMER
    with pytest.raises(FrozenInstanceError):
        result.unmatched_rows = (1,)
