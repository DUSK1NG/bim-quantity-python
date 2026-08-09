"""Inspect one IFC file and export the thin reader result.

This entry point intentionally contains no IFC parsing or quantity logic.  It
loads the validated project configuration, delegates all reading to
``src.ifc_reader.read_ifc``, and serializes the returned DataFrame and
diagnostics for a human to inspect.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_loader import load_project_config
from src.ifc_reader import IfcReaderError, IfcReaderUnavailable, read_ifc


def build_parser() -> argparse.ArgumentParser:
    """Build the three-path IFC inspection argument parser."""

    parser = argparse.ArgumentParser(
        description="检查 IFC 文件并导出标准构件明细与诊断报告（可选功能）"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("model.ifc"),
        help="输入 IFC 文件（默认：model.ifc）",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs"),
        help="七个配置文件所在目录（默认：configs）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/ifc"),
        help="IFC 输出目录（默认：outputs/ifc）",
    )
    return parser


def _resolve(path: Path) -> Path:
    """Resolve a relative CLI path against the repository root."""

    return path if path.is_absolute() else REPO_ROOT / path


def _diagnostics_payload(input_path: Path, result: Any) -> dict[str, Any]:
    """Build the stable, basename-only JSON diagnostics contract."""

    diagnostics = [str(item) for item in result.diagnostics]
    return {
        "source_file": input_path.name,
        "total_rows": int(len(result.frame)),
        "diagnostics": diagnostics,
    }


def _write_outputs(result: Any, input_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Write the reader frame and diagnostics using deterministic encodings."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    csv_path = output_dir / f"{stem}_ifc_elements.csv"
    diagnostics_path = output_dir / f"{stem}_ifc_diagnostics.json"

    result.frame.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    diagnostics_path.write_text(
        json.dumps(
            _diagnostics_payload(input_path, result),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path, diagnostics_path


def _completion_code(result: Any) -> int:
    """Return 2 only when rows exist alongside an ``Error:`` diagnostic."""

    diagnostics = (str(item).strip() for item in result.diagnostics)
    has_error = any(item.startswith("Error:") for item in diagnostics)
    return 2 if has_error and not result.frame.empty else 0


def _print_failure(exc: Exception) -> None:
    """Print a concise Chinese repair hint without a traceback."""

    print(f"错误：{exc}", file=sys.stderr)
    if isinstance(exc, IfcReaderUnavailable):
        print(
            "修复建议：请安装 requirements-ifc.txt；如不使用 IFC，可继续使用 CSV。",
            file=sys.stderr,
        )
    elif isinstance(exc, IfcReaderError):
        print(
            "修复建议：请检查 IFC 输入文件后重试；CSV 主流程仍可继续使用。",
            file=sys.stderr,
        )
    else:
        print(
            "修复建议：请检查输入 IFC、配置目录和输出目录后重试。",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    """Run the thin IFC inspection workflow and return its stable exit code."""

    args = build_parser().parse_args(argv)
    input_path = _resolve(args.input)
    config_dir = _resolve(args.config_dir)
    output_dir = _resolve(args.output_dir)

    try:
        config = load_project_config(config_dir)
        result = read_ifc(input_path, config)
        csv_path, diagnostics_path = _write_outputs(result, input_path, output_dir)
    except Exception as exc:  # noqa: BLE001 - CLI boundary maps all failures to 1
        _print_failure(exc)
        return 1

    print(
        f"IFC 检查完成：{len(result.frame)} 行，诊断 {len(result.diagnostics)} 条"
    )
    print(f"标准明细：{csv_path.name}")
    print(f"诊断报告：{diagnostics_path.name}")
    return _completion_code(result)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_parser",
    "main",
]
