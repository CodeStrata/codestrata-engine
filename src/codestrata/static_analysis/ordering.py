"""Deterministic ordering and identity helpers for findings."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.models.enums import FindingSource, Severity
from codestrata.models.finding import Finding

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


def finding_sort_key(finding: Finding) -> tuple[object, ...]:
    """Return a deterministic sort key for native and provider findings."""

    evidence = finding.evidence[0] if finding.evidence else None
    provider = str(finding.metadata.get("provider_id") or finding.source.value)
    file_path = evidence.file_path if evidence is not None else ""
    line_number = evidence.line_number if evidence is not None else 0
    return (
        _SEVERITY_ORDER.get(finding.severity, 99),
        finding.category.value,
        provider,
        finding.rule_id or "",
        file_path,
        line_number or 0,
        finding.title,
    )


def sort_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Sort findings deterministically."""

    return sorted(findings, key=finding_sort_key)


def external_finding_identity(finding: Finding) -> str | None:
    """Return a stable identity for external static-analysis findings."""

    if finding.source != FindingSource.EXTERNAL_STATIC_ANALYSIS:
        return None

    evidence = finding.evidence[0] if finding.evidence else None
    provider_id = str(finding.metadata.get("provider_id") or "")
    external_rule_id = str(finding.metadata.get("external_rule_id") or finding.rule_id or "")
    file_path = evidence.file_path if evidence is not None else ""
    line_number = evidence.line_number if evidence is not None else ""
    column_number = evidence.column_number if evidence is not None else ""
    message = (finding.description or "").strip().lower()
    return (
        f"ext:{provider_id}|{external_rule_id}|{file_path}|{line_number}|{column_number}|{message}"
    )


def deduplicate_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Remove duplicate external findings using stable identity keys."""

    seen: set[str] = set()
    unique: list[Finding] = []

    for finding in findings:
        identity = external_finding_identity(finding)
        if identity is None:
            unique.append(finding)
            continue
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(finding)

    return unique
