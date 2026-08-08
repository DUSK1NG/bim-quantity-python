"""Clean a standard elements CSV and write its quality report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_loader import load_project_config
from src.csv_reader import read_elements_csv
from src.data_cleaner import clean_elements
from src.quality_report import write_quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="清洗标准工程量 CSV 并生成质量报告")
    parser.add_argument("--input", type=Path, default=Path("data/sample/sample_elements.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--report-dir", type=Path, default=Path("outputs/reports"))
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = args.input if args.input.is_absolute() else REPO_ROOT / args.input
    config_dir = args.config_dir if args.config_dir.is_absolute() else REPO_ROOT / args.config_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    report_dir = args.report_dir if args.report_dir.is_absolute() else REPO_ROOT / args.report_dir

    config = load_project_config(config_dir)
    frame = read_elements_csv(input_path)
    result = clean_elements(frame, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    cleaned_path = output_dir / f"{stem}_clean.csv"
    report_path = report_dir / f"{stem}_quality_report.json"
    result.frame.to_csv(cleaned_path, index=False, encoding="utf-8-sig")
    write_quality_report(result.report, report_path, input_path.name)

    print(f"清洗完成：{result.report.total_rows} 行，问题行 {result.report.issue_rows} 行")
    print(f"清洗文件：{cleaned_path.name}")
    print(f"质量报告：{report_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
