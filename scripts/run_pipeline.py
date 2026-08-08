"""Run the deterministic quantity pipeline and write intermediate artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipeline import PipelineArtifacts, run_pipeline
from src.quality_report import write_quality_report


def build_parser() -> argparse.ArgumentParser:
    """Build the shared stage 3.3 pipeline argument parser."""

    parser = argparse.ArgumentParser(
        description="运行 BIM 工程量 Pipeline 并写出标准明细、质量报告和汇总 CSV"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/sample/sample_elements.csv"),
        help="输入标准工程量 CSV（默认：data/sample/sample_elements.csv）",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs"),
        help="七个配置文件所在目录（默认：configs）",
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=None,
        help="可选人工复核 CSV（默认：不读取）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/pipeline"),
        help="中间结果输出目录（默认：outputs/pipeline）",
    )
    return parser


def _resolve(path: Path | None) -> Path | None:
    """Resolve a CLI path against the repository root without changing names."""

    if path is None:
        return None
    return path if path.is_absolute() else REPO_ROOT / path


def _write_outputs(
    artifacts: PipelineArtifacts,
    input_path: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Serialize the three intermediate files from one pipeline result."""

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    standard_path = output_dir / f"{stem}_standard.csv"
    quality_path = output_dir / f"{stem}_quality_report.json"
    summary_path = output_dir / f"{stem}_summary.csv"

    artifacts.standard_frame.to_csv(
        standard_path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    write_quality_report(artifacts.quality_report, quality_path, artifacts.source_file)
    artifacts.cost_summary.to_csv(
        summary_path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    return standard_path, quality_path, summary_path


def _completion_code(artifacts: PipelineArtifacts) -> int:
    """Return 2 only when the completed report contains Error findings."""

    errors = int(artifacts.quality_report.counts_by_severity.get("Error", 0))
    return 2 if errors > 0 else 0


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline, report output locations, and preserve exit semantics."""

    args = build_parser().parse_args(argv)
    input_path = _resolve(args.input)
    config_dir = _resolve(args.config_dir)
    manual_path = _resolve(args.manual)
    output_dir = _resolve(args.output_dir)
    assert input_path is not None
    assert config_dir is not None
    assert output_dir is not None

    try:
        artifacts = run_pipeline(input_path, config_dir, manual_path)
        standard_path, quality_path, summary_path = _write_outputs(
            artifacts,
            input_path,
            output_dir,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary must return a stable code
        print(f"错误：{exc}", file=sys.stderr)
        print(
            "修复建议：请检查输入 CSV、配置目录和输出目录后重试。",
            file=sys.stderr,
        )
        return 1

    print(
        f"Pipeline 完成：{artifacts.quality_report.total_rows} 行，"
        f"问题行 {artifacts.quality_report.issue_rows} 行，"
        f"示例总价 {artifacts.overview.get('total_cost')}"
    )
    print(f"标准明细：{standard_path.name}")
    print(f"质量报告：{quality_path.name}")
    print(f"汇总文件：{summary_path.name}")
    return _completion_code(artifacts)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
