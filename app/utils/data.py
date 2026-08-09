"""Streamlit-safe byte loading for the deterministic quantity pipeline.

The Streamlit layer accepts uploaded bytes rather than paths.  Inputs are
written to a short-lived, controlled temporary directory and then handed to
``src.pipeline.run_pipeline`` so there is only one implementation of the
calculation and quality rules.
"""

from __future__ import annotations

import tempfile
from pathlib import Path, PurePosixPath
from typing import Final

import streamlit as st

from src.pipeline import PipelineArtifacts, PipelineError, run_pipeline


_DEFAULT_SOURCE_NAME: Final[str] = "uploaded.csv"
_MANUAL_SOURCE_NAME: Final[str] = "manual_validation.csv"


class DataLoadError(ValueError):
    """A user-provided CSV could not be loaded with an actionable hint."""


def _safe_basename(source_name: str) -> str:
    """Return a platform-neutral basename suitable for a temp-file name."""

    normalized = str(source_name or "").strip().replace("\\", "/")
    basename = PurePosixPath(normalized).name
    if basename in {"", ".", ".."}:
        return _DEFAULT_SOURCE_NAME
    return basename


def _repair_hint(error: Exception) -> str:
    """Build a Chinese repair hint without exposing temporary paths."""

    detail = str(error).strip()
    if detail:
        return f"数据加载失败：{detail}；请检查 UTF-8 编码、CSV 表头和必需列后重试。"
    return "数据加载失败；请检查 UTF-8 编码、CSV 表头和必需列后重试。"


@st.cache_data(ttl="15m", max_entries=20)
def _load_artifacts_cached(
    content: bytes,
    source_name: str,
    config_dir: str,
    manual_content: bytes | None,
) -> PipelineArtifacts:
    """Load one byte payload and cache its serializable pipeline artifacts."""

    safe_source_name = _safe_basename(source_name)
    try:
        with tempfile.TemporaryDirectory(prefix="bim-quantity-") as temporary_dir:
            temporary_root = Path(temporary_dir)
            input_path = temporary_root / safe_source_name
            input_path.write_bytes(content)

            manual_path: Path | None = None
            if manual_content is not None:
                manual_path = temporary_root / _MANUAL_SOURCE_NAME
                manual_path.write_bytes(manual_content)

            return run_pipeline(input_path, Path(config_dir), manual_path)
    except DataLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - loader boundary is user-facing
        raise DataLoadError(_repair_hint(exc)) from exc


def load_artifacts_from_bytes(
    content: bytes,
    source_name: str,
    config_dir: Path,
    manual_content: bytes | None = None,
) -> PipelineArtifacts:
    """Load elements and optional manual-review bytes through ``run_pipeline``.

    The public boundary normalizes the cache key to immutable values while
    retaining a typed ``Path`` interface for callers.  Temporary files are
    always removed when the cached helper completes or raises.
    """

    if not isinstance(content, bytes):
        raise DataLoadError("输入内容必须是 bytes；请重新选择 CSV 文件后重试。")
    if manual_content is not None and not isinstance(manual_content, bytes):
        raise DataLoadError("人工复核表内容必须是 bytes；请重新选择 CSV 文件后重试。")

    try:
        config_path = Path(config_dir)
    except (TypeError, ValueError) as exc:
        raise DataLoadError(_repair_hint(exc)) from exc

    try:
        return _load_artifacts_cached(
            bytes(content),
            _safe_basename(source_name),
            str(config_path),
            None if manual_content is None else bytes(manual_content),
        )
    except DataLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - keep the public error contract
        raise DataLoadError(_repair_hint(exc)) from exc


__all__ = ["DataLoadError", "load_artifacts_from_bytes"]
