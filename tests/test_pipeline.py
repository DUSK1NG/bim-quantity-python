"""Contract tests for the stage 3.3 quantity pipeline."""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"
SAMPLE = ROOT / "data" / "sample" / "sample_elements.csv"
MANUAL = ROOT / "data" / "sample" / "sample_manual_validation.csv"
FIELD_ORDER = [
    "element_id",
    "guid",
    "source",
    "ifc_class",
    "category",
    "element_name",
    "type_name",
    "level",
    "material",
    "length_m",
    "area_m2",
    "volume_m3",
    "quantity",
    "unit",
    "unit_price",
    "total_cost",
    "quantity_source",
    "quality_status",
    "raw_unit",
    "raw_row_number",
    "source_file",
    "exception_tags",
]


def _pipeline_module():
    """Import the production module as a RED-phase guard."""

    try:
        return importlib.import_module("src.pipeline")
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase guard
        pytest.fail(f"pipeline module is not available yet: {exc}")


def test_run_pipeline_returns_standard_artifacts_and_manual_validation() -> None:
    """The fixed sample flows through every stage without dropping rows."""

    pipeline = _pipeline_module()
    original_bytes = SAMPLE.read_bytes()

    artifacts = pipeline.run_pipeline(SAMPLE, CONFIG_DIR, MANUAL)

    assert isinstance(artifacts, pipeline.PipelineArtifacts)
    assert artifacts.standard_frame.shape == (240, 22)
    assert list(artifacts.standard_frame.columns) == FIELD_ORDER
    assert artifacts.source_file == SAMPLE.name
    assert artifacts.quality_report.total_rows == 240
    assert artifacts.quality_report.issue_rows > 0
    assert artifacts.quality_report.issues
    assert artifacts.overview["source_file"] == SAMPLE.name
    assert artifacts.overview["total_rows"] == 240
    assert artifacts.overview["issue_rows"] == artifacts.quality_report.issue_rows
    assert artifacts.overview["total_cost"] is not None
    assert not artifacts.by_level.empty
    assert not artifacts.by_category.empty
    assert not artifacts.by_material.empty
    assert not artifacts.cost_summary.empty
    assert len(artifacts.validation_result.details) == len(
        pd.read_csv(MANUAL, encoding="utf-8-sig")
    )
    assert not artifacts.validation_result.summary_by_category.empty
    assert artifacts.disclaimer == "本项目单价为教学示例数据，不用于正式工程造价。"

    # All stages operate on copies; the source CSV must remain byte-identical.
    assert SAMPLE.read_bytes() == original_bytes


def test_run_pipeline_without_manual_table_returns_empty_validation_result() -> None:
    """Manual review is optional and missing input yields a typed empty result."""

    pipeline = _pipeline_module()

    artifacts = pipeline.run_pipeline(SAMPLE, CONFIG_DIR)

    assert artifacts.validation_result.details.empty
    assert artifacts.validation_result.summary_by_category.empty
    assert artifacts.validation_result.messages == ()


def test_run_pipeline_wraps_missing_input_as_readable_pipeline_error(tmp_path: Path) -> None:
    """A missing elements CSV is a fatal, user-facing PipelineError."""

    pipeline = _pipeline_module()
    missing = tmp_path / "missing.csv"

    with pytest.raises(pipeline.PipelineError, match="CSV 文件不存在|输入") as exc_info:
        pipeline.run_pipeline(missing, CONFIG_DIR)

    assert "Pipeline" in str(exc_info.value)


def test_run_pipeline_wraps_configuration_errors_as_pipeline_error(tmp_path: Path) -> None:
    """Configuration failures retain a Chinese repair hint at the boundary."""

    pipeline = _pipeline_module()
    missing_config = tmp_path / "configs"

    with pytest.raises(pipeline.PipelineError, match="配置|缺少") as exc_info:
        pipeline.run_pipeline(SAMPLE, missing_config)

    assert "Pipeline" in str(exc_info.value)
