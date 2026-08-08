"""Immutable quality findings and deterministic JSON serialization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


DISCLAIMER = "本项目单价为教学示例数据，不用于正式工程造价。"


@dataclass(frozen=True)
class QualityIssue:
    """One row-level quality finding."""

    raw_row_number: int
    rule_id: str
    severity: str
    field: str
    message: str


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


def quality_report_to_dict(
    report: QualityReport,
    source_file: str | Path,
) -> dict[str, Any]:
    """Convert a report to stable, JSON-compatible insertion-ordered data."""

    ordered_issues = sorted(
        report.issues,
        key=lambda issue: (issue.raw_row_number, issue.rule_id, issue.field),
    )
    return {
        "source_file": _basename(source_file),
        "total_rows": report.total_rows,
        "issue_rows": report.issue_rows,
        "clean_rows": report.clean_rows,
        "counts_by_rule": dict(sorted(report.counts_by_rule.items())),
        "counts_by_severity": dict(sorted(report.counts_by_severity.items())),
        "not_applicable_rules": list(report.not_applicable_rules),
        "issues": [asdict(issue) for issue in ordered_issues],
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
    "DISCLAIMER",
    "QualityIssue",
    "QualityReport",
    "quality_report_to_dict",
    "write_quality_report",
]
