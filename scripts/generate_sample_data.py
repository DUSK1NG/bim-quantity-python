"""Generate the deterministic CSV fixture used by the Phase 2 foundation.

The generator is intentionally narrow: it creates the six configured IFC
classes, applies the seven disjoint teaching anomalies, and writes two CSV
files.  All mapping and price lookups come from :class:`ProjectConfig`; this
module does not maintain a second copy of project rules.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_loader import ProjectConfig, load_project_config
from src.schema import STANDARD_COLUMNS, UNITS, SampleDataSpec


LOGGER = logging.getLogger(__name__)
DISCLAIMER = "本项目单价为教学示例数据，不用于正式工程造价。"
SOURCE_FILE = "data/sample/sample_elements.csv"
EXTRA_COLUMNS = ("raw_unit", "raw_row_number", "source_file", "exception_tags")
EXPECTED_FIELD_COUNT = len(STANDARD_COLUMNS) + len(EXTRA_COLUMNS)


@dataclass(frozen=True)
class SampleGenerationResult:
    """Paths and deterministic diagnostics returned after generation."""

    elements_path: Path
    manual_validation_path: Path
    rows: int
    seed: int
    sha256: str
    exception_counts: dict[str, int]


def _name_prefix(ifc_class: str, config: ProjectConfig) -> str:
    pattern = str(config.naming_rules["allowed_patterns"][ifc_class])
    prefix = pattern.removeprefix("^").split("-", 1)[0]
    if not prefix:
        raise ValueError(f"naming_rules.json has no usable prefix for {ifc_class}")
    return prefix


def _unit_for_class(ifc_class: str) -> str:
    """Return the specialised teaching unit for one configured IFC class."""

    if ifc_class in {"IfcDoor", "IfcWindow"}:
        return "樘"
    return "m³"


def _first_price_row(config: ProjectConfig, category: str, unit: str) -> pd.Series:
    candidates = config.unit_prices[
        (config.unit_prices["category"] == category)
        & (config.unit_prices["unit"] == unit)
    ]
    if candidates.empty:
        raise ValueError(
            f"No baseline teaching price for {category}/{unit}; "
            "add it to sample_unit_prices.csv."
        )
    return candidates.iloc[0]


def _base_rows(spec: SampleDataSpec, config: ProjectConfig) -> pd.DataFrame:
    """Build ordinary rows before applying the deliberately bad rows."""

    rng = random.Random(spec.seed)
    classes = [spec.ifc_classes[index % len(spec.ifc_classes)] for index in range(spec.rows)]
    levels = [spec.levels[index % len(spec.levels)] for index in range(spec.rows)]
    field_order = tuple(config.field_mapping["field_order"])
    if len(field_order) != EXPECTED_FIELD_COUNT:
        raise ValueError(
            "field_mapping.json field_order must contain the 18 standard "
            "and 4 sample-trace columns."
        )

    rows: list[dict[str, Any]] = []
    for index in range(spec.rows):
        ifc_class = classes[index]
        level = levels[index]
        category = str(config.category_mapping["ifc_class_to_category"][ifc_class])
        unit = _unit_for_class(ifc_class)
        price_row = _first_price_row(config, category, unit)
        material = str(price_row["material"])
        volume = round(rng.uniform(0.2, 8.0), 3)
        quantity = 1.0 if unit == "樘" else volume
        rows.append(
            {
                "element_id": f"E-{index + 1:04d}",
                "guid": f"GUID-{index + 1:04d}",
                "source": "CSV",
                "ifc_class": ifc_class,
                "category": category,
                "element_name": f"{_name_prefix(ifc_class, config)}-AA-{index + 1:03d}",
                "type_name": f"{ifc_class}-Standard",
                "level": level,
                "material": material,
                "length_m": round(rng.uniform(1.0, 12.0), 3),
                "area_m2": round(rng.uniform(0.5, 30.0), 3),
                "volume_m3": volume,
                "quantity": quantity,
                "unit": unit,
                "unit_price": float("nan"),
                "total_cost": float("nan"),
                "quantity_source": "CSV Schedule",
                "quality_status": "Pass",
                "raw_unit": unit,
                "raw_row_number": index + 2,
                "source_file": SOURCE_FILE,
                "exception_tags": "",
            }
        )
    frame = pd.DataFrame(rows, columns=list(field_order))
    if list(frame.columns[: len(STANDARD_COLUMNS)]) != list(STANDARD_COLUMNS):
        raise ValueError("field_mapping.json field_order does not match STANDARD_COLUMNS")
    return frame


def _mark(frame: pd.DataFrame, indices: list[int], tag: str) -> None:
    for index in indices:
        existing = str(frame.at[index, "exception_tags"])
        frame.at[index, "exception_tags"] = tag if not existing else f"{existing}|{tag}"


def _inject_exceptions(frame: pd.DataFrame) -> None:
    """Apply fixed, pairwise-disjoint row sets to the 240-row fixture."""

    _mark(frame, [0, 1, 2, 3, 4], "missing_material")
    frame.loc[[0, 1, 2, 3, 4], "material"] = ""

    _mark(frame, [5, 6, 7], "missing_level")
    frame.loc[[5, 6, 7], "level"] = ""

    for first, second in ((8, 9), (10, 11)):
        frame.at[second, "guid"] = frame.at[first, "guid"]
        _mark(frame, [first, second], "duplicate_guid")

    _mark(frame, [12, 13, 14, 15], "zero_volume")
    frame.loc[[12, 13, 14, 15], "volume_m3"] = 0.0
    frame.loc[[12, 13, 14, 15], "quantity"] = 0.0

    _mark(frame, [16, 17, 18], "invalid_name")
    frame.loc[[16, 17, 18], "element_name"] = "INVALID"

    _mark(frame, [19, 20], "invalid_unit")
    frame.loc[[19, 20], "unit"] = "unknown"
    frame.loc[[19, 20], "raw_unit"] = "unknown"

    _mark(frame, [21, 22], "unmatched_unit_price")
    frame.loc[[21, 22], "material"] = "未知材料"


def _fill_prices(frame: pd.DataFrame, config: ProjectConfig) -> None:
    """Fill only exact category/material/unit teaching-price matches."""

    price_rows = config.unit_prices.set_index(["category", "material", "unit"])[
        "unit_price"
    ]
    for index, row in frame.iterrows():
        key = (row["category"], row["material"], row["unit"])
        if key not in price_rows.index:
            continue
        unit_price = float(price_rows.loc[key])
        frame.at[index, "unit_price"] = unit_price
        frame.at[index, "total_cost"] = round(float(row["quantity"]) * unit_price, 3)


def _exception_counts(frame: pd.DataFrame, config: ProjectConfig) -> dict[str, int]:
    """Return diagnostics derived from emitted values, never from tags."""

    invalid_names = set(config.naming_rules["invalid_name_examples"])
    valid_units = set(UNITS)
    duplicate_rows = frame["guid"].duplicated(keep=False)
    duplicate_groups = int(frame.loc[duplicate_rows, "guid"].nunique())
    return {
        "missing_material": int(frame["material"].eq("").sum()),
        "missing_level": int(frame["level"].eq("").sum()),
        "duplicate_guid": int(duplicate_rows.sum()),
        "duplicate_guid_groups": duplicate_groups,
        "zero_volume": int(pd.to_numeric(frame["volume_m3"]).eq(0).sum()),
        "invalid_name": int(frame["element_name"].isin(invalid_names).sum()),
        "invalid_unit": int((~frame["unit"].isin(valid_units)).sum()),
        "unmatched_unit_price": int(frame["material"].eq("未知材料").sum()),
    }


def generate_sample_data(
    output_dir: Path,
    config_dir: Path,
    seed: int = 20260804,
    rows: int = 240,
) -> SampleGenerationResult:
    """Generate the fixed Phase 2 fixture and its manual-validation subset."""

    spec = SampleDataSpec(seed=seed, rows=rows)
    if spec.seed != 20260804 or spec.rows != 240:
        raise ValueError("Phase 2 sample data requires seed=20260804 and rows=240.")
    config = load_project_config(Path(config_dir))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = _base_rows(spec, config)
    _inject_exceptions(frame)
    _fill_prices(frame, config)

    elements_path = output_dir / "sample_elements.csv"
    frame.to_csv(elements_path, index=False, encoding="utf-8-sig", lineterminator="\n")

    manual = frame.iloc[::20][["guid", "ifc_class", "level", "quantity"]].copy()
    manual.rename(columns={"quantity": "auto_quantity"}, inplace=True)
    manual["manual_quantity"] = manual["auto_quantity"].round(2)
    manual["review_date"] = "2026-08-04"
    manual["data_status"] = "程序演示数据"
    manual["disclaimer"] = DISCLAIMER
    manual_path = output_dir / "sample_manual_validation.csv"
    manual.to_csv(manual_path, index=False, encoding="utf-8-sig", lineterminator="\n")

    digest = hashlib.sha256(elements_path.read_bytes()).hexdigest()
    counts = _exception_counts(frame, config)
    return SampleGenerationResult(
        elements_path=elements_path,
        manual_validation_path=manual_path,
        rows=len(frame),
        seed=spec.seed,
        sha256=digest,
        exception_counts=counts,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成固定种子程序演示数据")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "sample")
    parser.add_argument("--config-dir", type=Path, default=REPO_ROOT / "configs")
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--rows", type=int, default=240)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = generate_sample_data(args.output_dir, args.config_dir, args.seed, args.rows)
    LOGGER.info(
        "generated %s rows at %s (sha256=%s)",
        result.rows,
        result.elements_path,
        result.sha256,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
