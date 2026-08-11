"""Shared helpers for architecture conclusion policies."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from codestrata.application.architecture.conclusions.clustering import select_primary_finding
from codestrata.domain.architecture.conclusions.enums import (
    ConclusionMateriality,
    ConclusionStatus,
    ModernizationWave,
)
from codestrata.domain.architecture.conclusions.relationships import SeveritySummary
from codestrata.domain.findings import Finding
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.rules.enums import MatchEvidenceConfidence

_SEVERITY_RANK = {
    FindingSeverity.INFORMATIONAL: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}

_CONFIDENCE_RANK = {
    MatchEvidenceConfidence.LOW: 0,
    MatchEvidenceConfidence.MEDIUM: 1,
    MatchEvidenceConfidence.HIGH: 2,
    MatchEvidenceConfidence.CERTAIN: 3,
}

_RANK_TO_CONFIDENCE = {
    0: MatchEvidenceConfidence.LOW,
    1: MatchEvidenceConfidence.MEDIUM,
    2: MatchEvidenceConfidence.HIGH,
    3: MatchEvidenceConfidence.CERTAIN,
}


def finding_confidence(finding: Finding) -> MatchEvidenceConfidence:
    raw = str(finding.metadata.get("confidence", "medium")).lower()
    try:
        return MatchEvidenceConfidence(raw)
    except ValueError:
        return MatchEvidenceConfidence.MEDIUM


def build_severity_summary(findings: Sequence[Finding]) -> SeveritySummary:
    if not findings:
        return SeveritySummary(
            highest_severity="informational",
            severity_counts={},
            source_finding_count=0,
        )
    counts = Counter(item.severity.value for item in findings)
    highest = max(findings, key=lambda item: _SEVERITY_RANK.get(item.severity, 0))
    primary = select_primary_finding(findings)
    return SeveritySummary(
        highest_severity=highest.severity.value,
        severity_counts=dict(sorted(counts.items())),
        primary_finding_severity=primary.severity.value,
        source_finding_count=len(findings),
    )


def derive_confidence(
    findings: Sequence[Finding],
    *,
    classification_coverage: float | None = None,
    essential_finding_ids: Sequence[str] | None = None,
) -> MatchEvidenceConfidence:
    """Conservative: do not exceed weakest essential finding confidence."""

    if not findings:
        return MatchEvidenceConfidence.LOW
    essential = set(essential_finding_ids or [item.id for item in findings])
    essential_findings = [item for item in findings if item.id in essential] or list(findings)
    ranks = [_CONFIDENCE_RANK[finding_confidence(item)] for item in essential_findings]
    rank = min(ranks)
    if classification_coverage is not None and classification_coverage < 0.25:
        rank = min(rank, _CONFIDENCE_RANK[MatchEvidenceConfidence.LOW])
    elif classification_coverage is not None and classification_coverage < 0.5:
        rank = min(rank, _CONFIDENCE_RANK[MatchEvidenceConfidence.MEDIUM])
    return _RANK_TO_CONFIDENCE[rank]


def derive_materiality(
    findings: Sequence[Finding],
    *,
    reinforcing_count: int = 0,
) -> ConclusionMateriality:
    if not findings:
        return ConclusionMateriality.UNDETERMINED
    summary = build_severity_summary(findings)
    highest = summary.highest_severity
    if reinforcing_count >= 1 and highest in {"high", "critical"}:
        return ConclusionMateriality.MATERIAL
    if reinforcing_count >= 1 or highest == "high":
        return ConclusionMateriality.NOTABLE
    if highest == "medium":
        return ConclusionMateriality.CONTEXTUAL
    if highest in {"low", "informational"}:
        return ConclusionMateriality.INFORMATIONAL
    return ConclusionMateriality.UNDETERMINED


def derive_status(
    *,
    confidence: MatchEvidenceConfidence,
    classification_coverage: float | None,
) -> ConclusionStatus:
    if classification_coverage is not None and classification_coverage < 0.25:
        return ConclusionStatus.PROVISIONAL
    if confidence is MatchEvidenceConfidence.LOW:
        return ConclusionStatus.PROVISIONAL
    return ConclusionStatus.ESTABLISHED


def coverage_map(
    *,
    extraction_coverage: float | None = None,
    classification_coverage: float | None = None,
) -> dict[str, str]:
    payload: dict[str, str] = {}
    if extraction_coverage is not None:
        payload["extraction_coverage"] = f"{extraction_coverage:.4f}"
    if classification_coverage is not None:
        payload["classification_coverage"] = f"{classification_coverage:.4f}"
    return payload


def default_limitations() -> tuple[str, ...]:
    return (
        "Based on static dependency analysis only.",
        "Does not establish production reliability.",
        "Business impact remains unknown without explicit enterprise context.",
    )


def wave_for_category(category: str) -> ModernizationWave:
    if "insufficient" in category:
        return ModernizationWave.WAVE_0_VALIDATE
    if "coupling" in category or "modularity" in category:
        return ModernizationWave.WAVE_2_FOUNDATION
    if "boundary" in category or "dependency" in category or "framework" in category:
        return ModernizationWave.WAVE_2_FOUNDATION
    return ModernizationWave.WAVE_2_FOUNDATION


def scope_from_findings(findings: Sequence[Finding]) -> tuple[str, ...]:
    scopes: set[str] = set()
    noise = {
        "cycle",
        "application",
        "infrastructure",
        "domain",
        "presentation",
        "persistence",
        "api",
        "config",
        "test",
    }
    for finding in findings:
        raw = finding.metadata.get("subject_keys")
        tokens: list[str] = []
        if isinstance(raw, (list, tuple)):
            tokens = [str(item).lower() for item in raw if str(item).strip()]
        elif isinstance(raw, str) and raw.strip():
            tokens = [part.strip().lower() for part in raw.split(",") if part.strip()]
        for token in tokens:
            if token in noise or token.startswith("out:") or token.startswith("share:"):
                continue
            scopes.add(token)
    return tuple(sorted(scopes))
