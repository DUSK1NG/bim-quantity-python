"""Independent acceptance tests for the deterministic Phase 2 sample data."""

from __future__ import annotations

from hashlib import sha256
from itertools import combinations
from pathlib import Path

import pandas as pd
import pytest

from scripts.generate_sample_data import generate_sample_data
from src.schema import STANDARD_COLUMNS


CONFIG_DIR = Path(__file__).parents[1] / "configs"
EXPECTED_COLUMNS = list(STANDARD_COLUMNS) + [
    "raw_unit",
    "raw_row_number",
    "source_file",
    "exception_tags",
]
VALID_UNITS = {"m", "m²", "m³", "个", "樘"}
DISCLAIMER = "本项目单价为教学示例数据，不用于正式工程造价。"


@pytest.fixture()
def generated_sample(tmp_path: Path):
    return generate_sample_data(tmp_path / "sample", CONFIG_DIR)


def _read_elements(path: Path) -> pd.DataFrame:
    """Read the generated file as a consumer would, retaining empty strings."""

    return pd.read_csv(path, keep_default_na=False)


def test_seeded_generation_is_240_rows_and_reproducible(tmp_path: Path):
    first = generate_sample_data(tmp_path / "one", CONFIG_DIR)
    second = generate_sample_data(tmp_path / "two", CONFIG_DIR)
    first_bytes = first.elements_path.read_bytes()
    second_bytes = second.elements_path.read_bytes()

    assert first.rows == second.rows == 240
    assert first.seed == second.seed == 20260804
    assert sha256(first_bytes).hexdigest() == sha256(second_bytes).hexdigest()
    assert first.sha256 == sha256(first_bytes).hexdigest()
    assert first.manual_validation_path.read_bytes() == second.manual_validation_path.read_bytes()


def test_sample_has_contract_columns_and_required_coverage(generated_sample):
    frame = _read_elements(generated_sample.elements_path)

    assert len(frame) == 240
    assert list(frame.columns) == EXPECTED_COLUMNS
    assert set(frame["level"]) == {"一层", "二层", "三层", ""}
    assert set(frame["ifc_class"]) == {
        "IfcBeam",
        "IfcColumn",
        "IfcSlab",
        "IfcWall",
        "IfcDoor",
        "IfcWindow",
    }
    assert set(frame["source"]) == {"CSV"}
    assert set(frame["quantity_source"]) == {"CSV Schedule"}
    assert frame["raw_row_number"].tolist() == list(range(2, 242))


def test_sample_has_exact_independently_recomputed_exception_counts(generated_sample):
    frame = _read_elements(generated_sample.elements_path)
    exception_rows = {
        "missing_material": set(frame.loc[frame["material"].eq(""), "raw_row_number"]),
        "missing_level": set(frame.loc[frame["level"].eq(""), "raw_row_number"]),
        "duplicate_guid": set(
            frame.loc[frame["guid"].duplicated(keep=False), "raw_row_number"]
        ),
        "zero_volume": set(
            frame.loc[pd.to_numeric(frame["volume_m3"]).eq(0), "raw_row_number"]
        ),
        "invalid_name": set(frame.loc[frame["element_name"].eq("INVALID"), "raw_row_number"]),
        "invalid_unit": set(
            frame.loc[~frame["unit"].isin(VALID_UNITS), "raw_row_number"]
        ),
        "unmatched_unit_price": set(
            frame.loc[frame["material"].eq("未知材料"), "raw_row_number"]
        ),
    }
    assert {name: len(rows) for name, rows in exception_rows.items()} == {
        "missing_material": 5,
        "missing_level": 3,
        "duplicate_guid": 4,
        "zero_volume": 4,
        "invalid_name": 3,
        "invalid_unit": 2,
        "unmatched_unit_price": 2,
    }
    for left, right in combinations(exception_rows.values(), 2):
        assert left.isdisjoint(right)

    duplicate = frame.loc[frame["guid"].duplicated(keep=False), "guid"]
    assert duplicate.nunique() == 2
    assert sorted(duplicate.value_counts().tolist()) == [2, 2]


def test_sample_uses_configured_prices_and_leaves_unknown_prices_blank(generated_sample):
    frame = _read_elements(generated_sample.elements_path)
    prices = pd.read_csv(CONFIG_DIR / "sample_unit_prices.csv")
    lookup = {
        (row.category, row.material, row.unit): float(row.unit_price)
        for row in prices.itertuples(index=False)
    }

    known_rows = frame[
        frame["material"].ne("")
        & frame["material"].ne("未知材料")
        & frame["unit"].isin(VALID_UNITS)
    ]
    for row in known_rows.itertuples(index=False):
        key = (row.category, row.material, row.unit)
        assert key in lookup
        assert float(row.unit_price) == lookup[key]
        assert float(row.total_cost) == pytest.approx(
            float(row.quantity) * lookup[key], abs=0.001
        )

    unmatched = frame[frame["material"].eq("未知材料")]
    assert len(unmatched) == 2
    assert unmatched["unit_price"].eq("").all()
    assert unmatched["total_cost"].eq("").all()


def test_manual_validation_preserves_automatic_values_and_disclaimer(generated_sample):
    manual = pd.read_csv(generated_sample.manual_validation_path, keep_default_na=False)

    assert len(manual) >= 12
    assert {
        "guid",
        "ifc_class",
        "level",
        "auto_quantity",
        "manual_quantity",
        "review_date",
        "data_status",
        "disclaimer",
    } <= set(manual.columns)
    assert set(manual["data_status"]) == {"程序演示数据"}
    assert manual["disclaimer"].eq(DISCLAIMER).all()
    assert manual["auto_quantity"].notna().all()
    assert manual["manual_quantity"].notna().all()


def test_generator_result_counts_are_diagnostics_not_csv_ground_truth(generated_sample):
    frame = _read_elements(generated_sample.elements_path)
    assert generated_sample.exception_counts["missing_material"] == int(
        frame["material"].eq("").sum()
    )
    assert generated_sample.exception_counts["duplicate_guid_groups"] == 2
    assert "exception_tags" in frame.columns


def test_sample_document_contains_exact_disclaimer_and_exception_counts():
    text = (Path(__file__).parents[1] / "data" / "sample" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "程序演示数据" in text
    assert "缺失材料 5 条" in text
    assert "缺失楼层 3 条" in text
    assert "重复 GUID 2 组" in text
    assert "体积为零 4 条" in text
    assert "名称不符合规则 3 条" in text
    assert "单位异常 2 条" in text
    assert "单价无法匹配 2 条" in text
    assert "本项目单价为教学示例数据，不用于正式工程造价。" in text


def test_phase_two_sample_and_docs_are_relative_path_safe():
    root = Path(__file__).parents[1]
    for path in (
        root / "README.md",
        root / "data" / "sample" / "README.md",
        root / "docs" / "data_dictionary.md",
        root / "docs" / "technical_route.md",
        root / "assets" / "README.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in text
        assert "C:/Users/" not in text
        assert "TODO" not in text
        assert "TBD" not in text
