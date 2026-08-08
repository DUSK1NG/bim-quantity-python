"""End-to-end tests for the stage 3.1 cleaning CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "clean_sample_data.py"
INPUT = ROOT / "data" / "sample" / "sample_elements.csv"


def _run(output_root: Path) -> tuple[Path, Path]:
    output_dir = output_root / "processed"
    report_dir = output_root / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(INPUT),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--config-dir",
            str(ROOT / "configs"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return (
        output_dir / "sample_elements_clean.csv",
        report_dir / "sample_elements_quality_report.json",
    )


def test_clean_cli_writes_repeatable_relative_outputs(tmp_path: Path) -> None:
    first_csv, first_report = _run(tmp_path / "one")
    second_csv, second_report = _run(tmp_path / "two")

    assert first_csv.read_bytes() == second_csv.read_bytes()
    assert first_report.read_bytes() == second_report.read_bytes()

    frame = pd.read_csv(first_csv, encoding="utf-8-sig")
    assert frame.shape == (240, 22)
    assert frame["source_file"].eq("sample_elements.csv").all()

    report_text = first_report.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert report["source_file"] == "sample_elements.csv"
    assert report["total_rows"] == 240
    assert report["disclaimer"] == "本项目单价为教学示例数据，不用于正式工程造价。"
    assert "\\" not in report_text
    assert "C:/Users/" not in report_text


def test_clean_cli_help_exposes_stage3_arguments() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    for option in ("--input", "--output-dir", "--report-dir", "--config-dir"):
        assert option in completed.stdout
