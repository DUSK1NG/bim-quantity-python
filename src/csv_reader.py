"""Read standard elements CSV files and add source traceability."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pandas as pd

from src.schema import STANDARD_COLUMNS


class CsvReaderError(ValueError):
    """A CSV could not be read or does not match the standard structure."""


def _file_name(path: Path) -> str:
    """Return a safe display name without exposing an absolute path."""

    return path.name or "<unnamed>"


def _read_header(path: Path) -> list[str]:
    """Read the first non-empty CSV row so duplicate names remain observable."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            for row in reader:
                if row:
                    return row
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CsvReaderError(
            f"CSV 文件表头读取失败：{_file_name(path)}；请检查 UTF-8 编码和 CSV 格式。"
        ) from exc
    return []


def _check_unique_columns(path: Path) -> None:
    header = _read_header(path)
    duplicates = sorted(name for name, count in Counter(header).items() if count > 1)
    if duplicates:
        names = "、".join(name or "<空列名>" for name in duplicates)
        raise CsvReaderError(
            f"CSV 文件存在重复列：{names}；请为每一列设置唯一列名。"
        )


def read_elements_csv(path: Path) -> pd.DataFrame:
    """读取并完成一个 elements CSV 的结构校验。"""

    csv_path = Path(path)
    name = _file_name(csv_path)
    try:
        exists = csv_path.is_file()
    except OSError as exc:
        raise CsvReaderError(f"CSV 文件检查失败：{name}；请确认文件可访问。") from exc
    if not exists:
        raise CsvReaderError(f"CSV 文件不存在：{name}；请检查输入路径。")

    try:
        frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise CsvReaderError(
            f"CSV 文件解析失败：{name}；请检查 UTF-8 编码、表头和行格式。"
        ) from exc

    _check_unique_columns(csv_path)
    if not frame.columns.is_unique:
        raise CsvReaderError(f"CSV 文件存在重复列：{name}；请为每一列设置唯一列名。")

    missing = [column for column in STANDARD_COLUMNS if column not in frame.columns]
    if missing:
        names = "、".join(missing)
        raise CsvReaderError(
            f"CSV 文件缺少标准列：{names}；请按 STANDARD_COLUMNS 补齐表头。"
        )

    frame["source"] = "CSV"
    frame["source_file"] = name
    frame["raw_row_number"] = range(1, len(frame) + 1)
    return frame


__all__ = ["CsvReaderError", "read_elements_csv"]
