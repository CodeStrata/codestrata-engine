"""Prioritized finding selection and token budgeting for AI context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from codestrata.models.enums import FindingSource, Severity
from codestrata.models.finding import Finding
from codestrata.static_analysis.visibility import CustomerVisibility


class AIContextBudgetError(ValueError):
    """Raised when critical AI evidence cannot fit in the context budget."""


class _PackTier(IntEnum):
    CRITICAL_HIGH_NATIVE = 0
    CRITICAL_HIGH_PRIMARY_PMD = 1
    MEDIUM_PRIMARY_PMD = 2
    MEDIUM_SUPPORTING_PMD = 3
    OTHER_NATIVE = 4
    LOW_INFORMATIONAL = 5


@dataclass(frozen=True, slots=True)
class FindingBudgetSelection:
    """Result of deterministic AI-context finding packing."""

    included: list[Finding]
    candidate_count: int
    included_count: int
    omitted_informational_count: int
    truncated: bool
    estimated_input_tokens: int


def estimate_tokens_for_text(text: str) -> int:
    """Rough deterministic token estimate (~4 characters per token)."""

    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def select_findings_for_ai_context(
    findings: list[Finding],
    *,
    max_findings: int,
    max_evidence_per_finding: int = 5,
) -> FindingBudgetSelection:
    """Select findings using modernization priority, never dropping critical/high."""

    candidates = [
        finding
        for finding in findings
        if _visibility(finding) != CustomerVisibility.SUPPRESSED_FROM_HTML.value
    ]
    ordered = sorted(candidates, key=_pack_sort_key)
    informational = [item for item in ordered if _is_informational(item)]
    non_informational = [item for item in ordered if not _is_informational(item)]

    must_include = [item for item in non_informational if _is_critical_or_high(item)]
    if len(must_include) > max_findings:
        raise AIContextBudgetError(
            "AI context budget cannot fit all critical/high findings "
            f"({len(must_include)} required, max_findings={max_findings})."
        )

    included: list[Finding] = list(must_include)
    remaining_slots = max_findings - len(included)

    for finding in non_informational:
        if remaining_slots <= 0:
            break
        if finding in included:
            continue
        included.append(finding)
        remaining_slots -= 1

    included_informational = 0
    if remaining_slots > 0:
        for finding in informational:
            if remaining_slots <= 0:
                break
            included.append(finding)
            included_informational += 1
            remaining_slots -= 1
    omitted_informational = len(informational) - included_informational

    # Stable final order by severity/source/visibility for the model.
    included = sorted(included, key=_display_sort_key)
    estimated = _estimate_selection_tokens(included, max_evidence_per_finding)
    return FindingBudgetSelection(
        included=included,
        candidate_count=len(candidates),
        included_count=len(included),
        omitted_informational_count=omitted_informational,
        truncated=len(included) < len(candidates),
        estimated_input_tokens=estimated,
    )


def _visibility(finding: Finding) -> str:
    return str(finding.metadata.get("customer_visibility") or CustomerVisibility.PRIMARY.value)


def _is_informational(finding: Finding) -> bool:
    if finding.severity == Severity.INFO:
        return True
    return _visibility(finding) == CustomerVisibility.INFORMATIONAL.value


def _is_critical_or_high(finding: Finding) -> bool:
    return finding.severity in {Severity.CRITICAL, Severity.HIGH}


def _is_pmd(finding: Finding) -> bool:
    return finding.source == FindingSource.EXTERNAL_STATIC_ANALYSIS


def _pack_tier(finding: Finding) -> int:
    visibility = _visibility(finding)
    if _is_critical_or_high(finding) and not _is_pmd(finding):
        return _PackTier.CRITICAL_HIGH_NATIVE
    if _is_critical_or_high(finding) and _is_pmd(finding):
        return _PackTier.CRITICAL_HIGH_PRIMARY_PMD
    if (
        finding.severity == Severity.MEDIUM
        and _is_pmd(finding)
        and visibility == CustomerVisibility.PRIMARY.value
    ):
        return _PackTier.MEDIUM_PRIMARY_PMD
    if (
        finding.severity == Severity.MEDIUM
        and _is_pmd(finding)
        and visibility == CustomerVisibility.SUPPORTING.value
    ):
        return _PackTier.MEDIUM_SUPPORTING_PMD
    if not _is_pmd(finding):
        return _PackTier.OTHER_NATIVE
    return _PackTier.LOW_INFORMATIONAL


def _pack_sort_key(finding: Finding) -> tuple[object, ...]:
    return (
        _pack_tier(finding),
        (finding.rule_id or "").lower(),
        finding.title.lower(),
        str(finding.id),
    )


def _display_sort_key(finding: Finding) -> tuple[object, ...]:
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    native_rank = 0 if not _is_pmd(finding) else 1
    visibility_rank = {
        CustomerVisibility.PRIMARY.value: 0,
        CustomerVisibility.SUPPORTING.value: 1,
        CustomerVisibility.INFORMATIONAL.value: 2,
    }
    return (
        severity_order.get(finding.severity, 99),
        native_rank,
        visibility_rank.get(_visibility(finding), 9),
        (finding.rule_id or "").lower(),
        finding.title.lower(),
    )


def _estimate_selection_tokens(findings: list[Finding], max_evidence: int) -> int:
    total = 0
    for finding in findings:
        blob = " ".join(
            [
                finding.rule_id or "",
                finding.title,
                finding.description,
                str(finding.metadata.get("group_id") or ""),
                str(finding.metadata.get("mapping_rationale") or ""),
            ]
        )
        for evidence in finding.evidence[:max_evidence]:
            blob += " ".join(
                [
                    evidence.file_path,
                    evidence.description or "",
                    str(evidence.line_number or ""),
                ]
            )
        total += estimate_tokens_for_text(blob)
    return total
