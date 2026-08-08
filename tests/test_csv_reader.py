"""Contract tests for the stage 3.1 CSV reader."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.schema import STANDARD_COLUMNS


ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "data" / "sample" / "sample_elements.csv"


def _reader_module():
    """Import the production module as a test failure until it exists."""

    try:
        return importlib.import_module("src.csv_reader")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"CSV reader module is not available yet: {exc}")


def test_reads_sample_rows_and_injects_traceability_columns() -> None:
    frame = _reader_module().read_elements_csv(SAMPLE)

    assert len(frame) == 240
    assert set(STANDARD_COLUMNS) <= set(frame.columns)
    assert frame["source"].eq("CSV").all()
    assert frame["source_file"].eq(SAMPLE.name).all()
    assert not frame["source_file"].str.contains(r"[\\/]").any()
    assert frame["raw_row_number"].tolist() == list(range(1, 241))


def test_missing_file_is_reported_as_csv_reader_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    reader = _reader_module()

    with pytest.raises(reader.CsvReaderError, match="文件.*不存在"):
        reader.read_elements_csv(missing)


def test_duplicate_column_names_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        "element_id,element_id,guid\nE-1,E-1,GUID-1\n",
        encoding="utf-8-sig",
    )
    reader = _reader_module()

    with pytest.raises(reader.CsvReaderError, match="重复.*列"):
        reader.read_elements_csv(duplicate)


def test_missing_standard_column_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing-column.csv"
    columns = [column for column in STANDARD_COLUMNS if column != "guid"]
    pd.DataFrame([{column: "value" for column in columns}]).to_csv(
        missing,
        index=False,
        encoding="utf-8-sig",
    )
    reader = _reader_module()

    with pytest.raises(reader.CsvReaderError, match="缺少.*guid"):
        reader.read_elements_csv(missing)


def test_parser_errors_are_reported_as_csv_reader_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken.csv"
    broken.write_text(",".join(STANDARD_COLUMNS) + '\n"unterminated\n', encoding="utf-8-sig")
    reader = _reader_module()

    with pytest.raises(reader.CsvReaderError, match="CSV.*解析"):
        reader.read_elements_csv(broken)
