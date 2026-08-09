"""Acceptance tests for the Streamlit byte-oriented data loader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.utils import data as data_module
from app.utils.data import DataLoadError, load_artifacts_from_bytes


ROOT = Path(__file__).parents[1]
CONFIG_DIR = ROOT / "configs"
SAMPLE = ROOT / "data" / "sample" / "sample_elements.csv"
MANUAL = ROOT / "data" / "sample" / "sample_manual_validation.csv"


def _frame_signature(frame: pd.DataFrame) -> str:
    """Serialize a result frame in a deterministic, index-free form."""

    return frame.to_json(orient="split", force_ascii=False, date_format="iso")


def _artifact_signature(artifacts) -> tuple[object, ...]:
    """Capture the calculated summary without comparing DataFrame objects."""

    report = artifacts.quality_report
    validation = artifacts.validation_result
    return (
        _frame_signature(artifacts.standard_frame),
        report.total_rows,
        report.issue_rows,
        report.clean_rows,
        tuple(sorted(report.counts_by_rule.items())),
        tuple(sorted(report.counts_by_severity.items())),
        tuple(report.not_applicable_rules),
        tuple(report.issues),
        artifacts.overview,
        _frame_signature(artifacts.by_level),
        _frame_signature(artifacts.by_category),
        _frame_signature(artifacts.by_material),
        _frame_signature(artifacts.cost_summary),
        _frame_signature(validation.details),
        _frame_signature(validation.summary_by_category),
        tuple(validation.messages),
        artifacts.source_file,
        artifacts.disclaimer,
    )


def test_sample_and_upload_bytes_produce_equivalent_pipeline_artifacts() -> None:
    """The same CSV bytes use the same deterministic pipeline path."""

    content = SAMPLE.read_bytes()

    sample_artifacts = load_artifacts_from_bytes(
        content,
        SAMPLE.name,
        CONFIG_DIR,
    )
    upload_artifacts = load_artifacts_from_bytes(
        bytes(content),
        SAMPLE.name,
        CONFIG_DIR,
    )

    assert _artifact_signature(sample_artifacts) == _artifact_signature(upload_artifacts)
    assert sample_artifacts.validation_result.details.empty


def test_manual_bytes_are_optional_and_source_trace_keeps_only_basename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual review is accepted and temporary input files are removed."""

    original_tempdir = data_module.tempfile.TemporaryDirectory
    created: list[Path] = []

    class TrackingTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            self._delegate = original_tempdir(*args, **kwargs)
            self.name = self._delegate.name
            created.append(Path(self.name))

        def __enter__(self):
            self._delegate.__enter__()
            return self.name

        def __exit__(self, *args):
            return self._delegate.__exit__(*args)

    monkeypatch.setattr(
        data_module.tempfile,
        "TemporaryDirectory",
        TrackingTemporaryDirectory,
    )

    artifacts = load_artifacts_from_bytes(
        SAMPLE.read_bytes(),
        r"incoming\nested\uploaded.csv",
        CONFIG_DIR,
        manual_content=MANUAL.read_bytes(),
    )

    assert artifacts.source_file == "uploaded.csv"
    assert artifacts.overview["source_file"] == "uploaded.csv"
    assert artifacts.standard_frame["source_file"].eq("uploaded.csv").all()
    assert not artifacts.validation_result.details.empty
    assert created
    assert all(not temporary_path.exists() for temporary_path in created)


def test_invalid_bytes_raise_chinese_repair_hint() -> None:
    """Malformed or non-UTF-8 bytes fail at the loader boundary."""

    with pytest.raises(DataLoadError, match="CSV|编码|UTF-8") as exc_info:
        load_artifacts_from_bytes(
            b"\xff\xfe\x00\x01",
            "broken.csv",
            CONFIG_DIR,
        )

    assert "请" in str(exc_info.value)
