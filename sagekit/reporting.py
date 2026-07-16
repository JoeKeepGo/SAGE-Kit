from __future__ import annotations

from dataclasses import dataclass

from .findings import Finding


DEFAULT_MAX_FINDINGS = 50
MAX_FINDINGS_LIMIT = 500
LEVEL_ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}


@dataclass(frozen=True)
class FindingReport:
    findings: tuple[Finding, ...]
    total: int
    displayed: int
    truncated: int
    by_level: dict[str, int]


def build_finding_report(
    findings: list[Finding],
    *,
    max_findings: int = DEFAULT_MAX_FINDINGS,
) -> FindingReport:
    if not 1 <= max_findings <= MAX_FINDINGS_LIMIT:
        raise ValueError(f"max_findings must be between 1 and {MAX_FINDINGS_LIMIT}")
    indexed = list(enumerate(findings))
    indexed.sort(key=lambda item: (LEVEL_ORDER[item[1].level], item[0]))
    displayed = tuple(finding for _, finding in indexed[:max_findings])
    counts = {
        level: sum(1 for finding in findings if finding.level == level)
        for level in ("FAIL", "PASS", "WARN")
    }
    return FindingReport(
        findings=displayed,
        total=len(findings),
        displayed=len(displayed),
        truncated=max(0, len(findings) - len(displayed)),
        by_level=counts,
    )


def finding_report_payload(report: FindingReport) -> dict[str, object]:
    return {
        "findings": [finding.to_json() for finding in report.findings],
        "summary": {
            "total": report.total,
            "displayed": report.displayed,
            "truncated": report.truncated,
            "by_level": dict(report.by_level),
        },
    }
