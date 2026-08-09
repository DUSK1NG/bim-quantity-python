"""Orchestrate the deterministic CSV quantity-calculation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

import pandas as pd

from src.aggregations import (
    build_overview,
    summarize_by_category,
    summarize_by_level,
    summarize_by_material,
    summarize_costs,
)
from src.config_loader import load_project_config
from src.cost_calculator import calculate_costs
from src.csv_reader import read_elements_csv
from src.data_cleaner import clean_elements
from src.quality_checker import check_quality
from src.quality_report import DISCLAIMER, QualityReport
from src.quantity_calculator import calculate_quantities
from src.schema import STANDARD_COLUMNS
from src.validation import ValidationResult, validate_manual_results


class PipelineError(ValueError):
    """A pipeline stage failed with a user-facing repair hint."""


@dataclass(frozen=True)
class PipelineArtifacts:
    """Immutable container for all outputs of one pipeline run."""

    standard_frame: pd.DataFrame
    quality_report: QualityReport
    validation_result: ValidationResult
    overview: dict[str, Any]
    by_level: pd.DataFrame
    by_category: pd.DataFrame
    by_material: pd.DataFrame
    cost_summary: pd.DataFrame
    source_file: str
    disclaimer: str


_T = TypeVar("_T")


def _stage(stage_name: str, operation: Callable[[], _T]) -> _T:
    """Run one operation and convert implementation errors at the boundary."""

    try:
        return operation()
    except PipelineError:
        raise
    except Exception as exc:  # noqa: BLE001 - boundary must preserve a readable cause
        raise PipelineError(f"Pipeline {stage_name}失败：{exc}") from exc


def _read_manual(path: Path) -> pd.DataFrame:
    """Read an optional manual review CSV using the same UTF-8 contract."""

    return pd.read_csv(path, encoding="utf-8-sig")


def _empty_manual_frame() -> pd.DataFrame:
    """Build the typed empty manual table accepted by the validator."""

    return pd.DataFrame(columns=["guid", "manual_quantity"])


def run_pipeline_from_frame(
    raw_frame: pd.DataFrame,
    config_dir: Path,
    source_file: str,
    manual_frame: pd.DataFrame | None = None,
) -> PipelineArtifacts:
    """Run the shared pipeline on an already-read CSV or IFC DataFrame."""

    if not isinstance(raw_frame, pd.DataFrame):
        raise PipelineError("Pipeline 输入必须是 pandas DataFrame；请检查 reader 输出。")
    missing = [column for column in STANDARD_COLUMNS if column not in raw_frame.columns]
    if missing:
        names = "、".join(missing)
        raise PipelineError(f"Pipeline 输入缺少标准列：{names}；请检查 reader 输出。")

    source_name = Path(str(source_file or "")).name or "uploaded.ifc"
    config_path = Path(config_dir)
    config = _stage("配置加载", lambda: load_project_config(config_path))
    cleaned = _stage("数据清洗", lambda: clean_elements(raw_frame.copy(deep=True), config))
    quantities = _stage(
        "工程量计算", lambda: calculate_quantities(cleaned.frame, config)
    )
    costs = _stage("造价计算", lambda: calculate_costs(quantities.frame, config))

    standard_frame = costs.frame
    quality_report = _stage(
        "质量检查", lambda: check_quality(standard_frame, config)
    )

    if manual_frame is None:
        manual_input = _empty_manual_frame()
    elif isinstance(manual_frame, pd.DataFrame):
        manual_input = manual_frame.copy(deep=True)
    else:
        raise PipelineError("人工复核输入必须是 pandas DataFrame；请检查上传内容。")
    validation_result = _stage(
        "人工复核", lambda: validate_manual_results(standard_frame, manual_input)
    )

    by_level = _stage("楼层汇总", lambda: summarize_by_level(standard_frame))
    by_category = _stage("类别汇总", lambda: summarize_by_category(standard_frame))
    by_material = _stage("材料汇总", lambda: summarize_by_material(standard_frame))
    cost_summary = _stage("造价汇总", lambda: summarize_costs(standard_frame))
    overview = _stage(
        "项目概览", lambda: build_overview(standard_frame, quality_report, source_name)
    )

    return PipelineArtifacts(
        standard_frame=standard_frame,
        quality_report=quality_report,
        validation_result=validation_result,
        overview=overview,
        by_level=by_level,
        by_category=by_category,
        by_material=by_material,
        cost_summary=cost_summary,
        source_file=source_name,
        disclaimer=DISCLAIMER,
    )


def run_pipeline(
    input_path: Path,
    config_dir: Path,
    manual_path: Path | None = None,
) -> PipelineArtifacts:
    """Run reader, cleaner, calculators, quality checks and aggregations."""

    source_path = Path(input_path)
    config_path = Path(config_dir)
    manual_file = Path(manual_path) if manual_path is not None else None
    raw_frame = _stage("CSV 读取", lambda: read_elements_csv(source_path))
    if manual_file is None:
        manual_frame = None
    else:
        manual_frame = _stage("人工复核表读取", lambda: _read_manual(manual_file))

    return run_pipeline_from_frame(raw_frame, config_path, source_path.name, manual_frame)


__all__ = [
    "PipelineArtifacts",
    "PipelineError",
    "run_pipeline",
    "run_pipeline_from_frame",
]
