"""Immutable quality findings and deterministic JSON serialization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


DISCLAIMER = "本项目单价为教学示例数据，不用于正式工程造价。"
ALLOWED_SEVERITIES = frozenset({"Info", "Warning", "Error"})
NOT_APPLICABLE_RULES: tuple[str, ...] = (
    "missing_section_size",
    "outlier_dimension",
)


@dataclass(frozen=True)
class QualityIssue:
    """One row-level quality finding."""

    raw_row_number: int
    rule_id: str
    severity: str
    field: str
    message: str
    source_file: str | None = None
    guid: str | None = None
    element_name: str | None = None
    type_name: str | None = None
    level: str | None = None
    suggestion: str | None = None


@dataclass(frozen=True)
class QualityReport:
    """Deterministic aggregate of row-level quality findings."""

    total_rows: int
    issue_rows: int
    clean_rows: int
    counts_by_rule: Mapping[str, int]
    counts_by_severity: Mapping[str, int]
    not_applicable_rules: tuple[str, ...]
    issues: tuple[QualityIssue, ...]


def _basename(source_file: str | Path) -> str:
    """Return a platform-neutral basename without exposing local paths."""

    normalized = str(source_file).replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _json_value(value: Any) -> Any:
    """Convert pandas scalar missing values to JSON ``null``."""

    if value is None:
        return None
    try:
        missing = pd.isna(value)
        if missing is pd.NA:
            return None
        if bool(missing):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _issue_to_dict(issue: QualityIssue) -> dict[str, Any]:
    """Serialize one issue while keeping trace paths and severities safe."""

    payload = asdict(issue)
    payload["severity"] = (
        issue.severity if issue.severity in ALLOWED_SEVERITIES else "Warning"
    )
    for name in ("source_file", "guid", "element_name", "type_name", "level", "suggestion"):
        value = _json_value(payload.get(name))
        if name == "source_file" and value is not None:
            value = _basename(value)
        payload[name] = value
    return payload


def _issue_sort_key(issue: QualityIssue) -> tuple[Any, str, str, str]:
    source_file = _json_value(issue.source_file)
    return (
        issue.raw_row_number,
        issue.rule_id,
        issue.field,
        "" if source_file is None else _basename(source_file),
    )


def quality_report_to_dict(
    report: QualityReport,
    source_file: str | Path,
) -> dict[str, Any]:
    """Convert a report to stable, JSON-compatible insertion-ordered data."""

    ordered_issues = sorted(report.issues, key=_issue_sort_key)
    counts_by_severity: dict[str, int] = {}
    for severity, count in report.counts_by_severity.items():
        normalized = severity if severity in ALLOWED_SEVERITIES else "Warning"
        counts_by_severity[normalized] = counts_by_severity.get(normalized, 0) + count
    return {
        "source_file": _basename(source_file),
        "total_rows": report.total_rows,
        "issue_rows": report.issue_rows,
        "clean_rows": report.clean_rows,
        "counts_by_rule": dict(sorted(report.counts_by_rule.items())),
        "counts_by_severity": dict(sorted(counts_by_severity.items())),
        "not_applicable_rules": list(NOT_APPLICABLE_RULES),
        "issues": [_issue_to_dict(issue) for issue in ordered_issues],
        "disclaimer": DISCLAIMER,
    }


def write_quality_report(
    report: QualityReport,
    path: Path,
    source_file: str | Path,
) -> None:
    """Write a UTF-8 JSON report with stable formatting and one final newline."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = quality_report_to_dict(report, source_file)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "ALLOWED_SEVERITIES",
    "DISCLAIMER",
    "NOT_APPLICABLE_RULES",
    "QualityIssue",
    "QualityReport",
    "quality_report_to_dict",
    "write_quality_report",
]
