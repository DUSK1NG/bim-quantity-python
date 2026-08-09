"""Contracts for the optional IFC inspection CLI.

The tests deliberately replace the reader/config boundary with small fakes.  A
base install must not need IfcOpenShell or a binary IFC file to exercise the
CLI's argument, serialization, and exit-code behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from src.schema import STANDARD_COLUMNS

from scripts import inspect_ifc


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "inspect_ifc.py"


def _fake_frame() -> pd.DataFrame:
    """Return one valid standard IFC row with a Chinese value for encoding checks."""

    values = {
        column: [pd.NA]
        for column in (*STANDARD_COLUMNS, "raw_unit", "raw_row_number", "source_file", "exception_tags")
    }
    values.update(
        {
            "element_id": ["B-001"],
            "guid": ["guid-001"],
            "source": ["IFC"],
            "ifc_class": ["IfcBeam"],
            "category": ["Beam"],
            "element_name": ["梁-中文"],
            "quantity_source": ["IFC BaseQuantity"],
            "quality_status": ["Pass"],
            "raw_unit": ["m"],
            "raw_row_number": [1],
            "source_file": ["model.ifc"],
            "exception_tags": [""],
        }
    )
    return pd.DataFrame(values)


def _patch_reader(
    monkeypatch,
    *,
    frame: pd.DataFrame | None = None,
    diagnostics: tuple[str, ...] = (),
    error: Exception | None = None,
) -> list[tuple[Path, object]]:
    """Patch the config/reader boundary and capture its exact call arguments."""

    calls: list[tuple[Path, object]] = []
    fake_config = object()

    monkeypatch.setattr(inspect_ifc, "load_project_config", lambda _path: fake_config)

    def fake_read(path: Path, config: object):
        calls.append((path, config))
        if error is not None:
            raise error
        return SimpleNamespace(
            frame=_fake_frame() if frame is None else frame,
            diagnostics=diagnostics,
        )

    monkeypatch.setattr(inspect_ifc, "read_ifc", fake_read)
    return calls


def test_inspect_ifc_help_exposes_the_three_documented_paths() -> None:
    """The executable help path works without optional dependencies."""

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--input" in completed.stdout
    assert "--config-dir" in completed.stdout
    assert "--output-dir" in completed.stdout
    assert "IFC" in completed.stdout or "检查" in completed.stdout


def test_inspect_ifc_writes_basename_bom_csv_and_diagnostics_json(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A clean fake result is serialized with stable names and UTF-8-SIG."""

    input_path = tmp_path / "nested" / "model.ifc"
    input_path.parent.mkdir()
    input_path.write_bytes(b"fake IFC")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    output_dir = tmp_path / "outputs" / "ifc"
    calls = _patch_reader(monkeypatch)

    code = inspect_ifc.main(
        [
            "--input",
            str(input_path),
            "--config-dir",
            str(config_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert code == 0
    assert calls == [(input_path, calls[0][1])]
    csv_path = output_dir / "model_ifc_elements.csv"
    diagnostics_path = output_dir / "model_ifc_diagnostics.json"
    assert csv_path.is_file()
    assert diagnostics_path.is_file()
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")

    exported = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert exported.loc[0, "element_name"] == "梁-中文"
    assert exported.loc[0, "source_file"] == "model.ifc"
    assert str(tmp_path) not in csv_path.read_text(encoding="utf-8-sig")

    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics == {
        "source_file": "model.ifc",
        "total_rows": 1,
        "diagnostics": [],
    }
    assert str(tmp_path) not in diagnostics_path.read_text(encoding="utf-8")
    output = capsys.readouterr().out
    assert "IFC" in output
    assert "model_ifc_elements.csv" in output
    assert "model_ifc_diagnostics.json" in output


def test_inspect_ifc_returns_two_for_error_diagnostics_with_rows(
    tmp_path: Path, monkeypatch
) -> None:
    """Recoverable reader diagnostics preserve output and use status 2."""

    input_path = tmp_path / "model.ifc"
    input_path.write_bytes(b"fake IFC")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    calls = _patch_reader(monkeypatch, diagnostics=("Error: 缺少楼层关系",))

    code = inspect_ifc.main(
        [
            "--input",
            str(input_path),
            "--config-dir",
            str(config_dir),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 2
    assert calls


def test_inspect_ifc_returns_one_with_chinese_guidance_for_missing_dependency(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Missing optional IfcOpenShell is a fatal CLI error with repair guidance."""

    input_path = tmp_path / "model.ifc"
    input_path.write_bytes(b"fake IFC")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    from src.ifc_reader import IfcReaderUnavailable

    _patch_reader(
        monkeypatch,
        error=IfcReaderUnavailable(
            "缺少 IfcOpenShell；请安装 requirements-ifc.txt，或继续使用 CSV。"
        ),
    )

    code = inspect_ifc.main(
        [
            "--input",
            str(input_path),
            "--config-dir",
            str(config_dir),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 1
    message = capsys.readouterr()
    combined = f"{message.out}\n{message.err}"
    assert "requirements-ifc.txt" in combined
    assert "CSV" in combined
    assert "错误" in combined or "修复" in combined


def test_inspect_ifc_returns_one_for_reader_input_error(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Invalid IFC input is reported as a stable Chinese CLI error."""

    input_path = tmp_path / "missing.ifc"
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    from src.ifc_reader import IfcReaderError

    _patch_reader(
        monkeypatch,
        error=IfcReaderError("输入 IFC 文件不存在；请检查路径后重试。"),
    )

    code = inspect_ifc.main(
        [
            "--input",
            str(input_path),
            "--config-dir",
            str(config_dir),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert code == 1
    captured = capsys.readouterr()
    combined = f"{captured.out}\n{captured.err}"
    assert "请检查" in combined or "修复" in combined


def test_inspect_ifc_returns_one_when_output_directory_cannot_be_written(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """An output filesystem failure is fatal and does not leak a traceback."""

    input_path = tmp_path / "model.ifc"
    input_path.write_bytes(b"fake IFC")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    output_path = tmp_path / "not-a-directory"
    output_path.write_text("occupied", encoding="utf-8")
    _patch_reader(monkeypatch)

    code = inspect_ifc.main(
        [
            "--input",
            str(input_path),
            "--config-dir",
            str(config_dir),
            "--output-dir",
            str(output_path),
        ]
    )

    assert code == 1
    captured = capsys.readouterr()
    combined = f"{captured.out}\n{captured.err}"
    assert "输出" in combined or "修复" in combined
    assert "Traceback" not in combined
