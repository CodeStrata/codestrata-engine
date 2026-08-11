"""Build AI Readiness Intelligence from existing report + findings (Epic 3 Slice 3.8).

Do NOT import from codestrata.reporting.html_v2 (circular import). Duck-type
findings/recommendations with Any + getattr.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporting.ai_readiness.intelligence_models import (
    AiReadinessCoverageRow,
    AiReadinessFindingLink,
    AiReadinessIntelligenceSection,
    AiReadinessOverviewFact,
    AiReadinessRecommendationLink,
    AiReadinessSignalFamily,
    AiReadinessSignalGroup,
    AiReadinessSignalRow,
)
from codestrata.reporting.ai_readiness.models import (
    AiReadinessReportCapabilityFamilyEntry,
    AiReadinessReportCoverageAreaView,
    AiReadinessReportSection,
)

_BASE_LIMITATIONS = (
    "Repository evidence only.",
    "No LLM or model execution.",
    "No model or prompt evaluation.",
    "No runtime AI behavior inspection.",
    "No data, retrieval, or vector quality assessment.",
    "No AI safety certification.",
    "No organizational readiness assessment.",
    "No governance maturity assessment.",
    "No numeric AI enablement score.",
    "Detected integrations do not prove production use.",
    "Absence of findings does not establish AI readiness.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "ai ready",
    "agent ready",
    "rag ready",
    "production ai ready",
    "production ready",
    "governed ai",
    "safe ai",
    "mature ai",
    "high-quality data",
    "strong ai foundation",
    "mature ai architecture",
    "no ai readiness risks",
    "no ai issues",
    "readiness score",
    "implement rag",
    "migrate to",
)

_EMPTY_FINDINGS_MESSAGE = (
    "No AI readiness findings were produced within the assessed repository "
    "scope. Agent execution, RAG suitability, and live AI runtime posture "
    "were not assessed. Absence of findings does not establish AI readiness."
)

_SAFE_STATUS_SUMMARY = (
    "AI readiness assessment completed using repository-observable evidence. "
    "Zero findings do not establish AI readiness. Detected integrations do "
    "not prove production use."
)

_SAFE_POSTURE_SUMMARY = (
    "Repository-observable AI-enablement signals were assessed from static "
    "evidence only. This does not establish AI readiness, agent readiness, "
    "or RAG readiness."
)

_CONFIDENCE_RANK = {
    "high": 3,
    "moderate": 2,
    "medium": 2,
    "limited": 1,
    "low": 1,
    "unavailable": 0,
    "unknown": 0,
}

_FAMILY_TITLES: dict[str, str] = {
    "api_boundaries": "API and service boundaries",
    "documentation_metadata": "Documentation and metadata",
    "data_retrieval": "Data access and retrieval signals",
    "ai_integrations": "Existing AI and LLM integrations",
    "tool_mcp": "Tool and MCP integration",
    "workflow_agents": "Workflow and agent boundaries",
    "observability_governance": "Observability and governance signals",
    "other": "Other AI-enablement signals",
}

_FAMILY_NOTES: dict[str, str] = {
    "api_boundaries": (
        "Detected API and service boundary signals do not establish "
        "suitability for AI or agents."
    ),
    "documentation_metadata": (
        "Detected documentation and metadata signals do not establish "
        "quality or completeness."
    ),
    "data_retrieval": (
        "Detected data access and retrieval signals do not establish RAG "
        "readiness or data quality."
    ),
    "ai_integrations": (
        "Detected AI and LLM integration signals do not prove production "
        "use, model quality, or safety."
    ),
    "tool_mcp": (
        "Detected tool and MCP integration signals do not establish agent "
        "readiness."
    ),
    "workflow_agents": (
        "Detected workflow and agent boundary signals do not establish "
        "autonomous or production maturity."
    ),
    "observability_governance": (
        "Detected observability and governance signals do not establish "
        "organizational governance, compliance, or safety."
    ),
    "other": (
        "Repository-observable AI-enablement signals were detected. "
        "They do not establish AI readiness."
    ),
}

_KNOWN_FAMILIES = frozenset(_FAMILY_TITLES) - {"other"}

_UNSAFE_PATH_FRAGMENTS = (
    "secret",
    "secrets",
    "prompt",
    "prompts",
    "api_key",
    "api-key",
    "apikey",
    ".env",
)


def build_ai_readiness_intelligence(
    report: AiReadinessReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> AiReadinessIntelligenceSection | None:
    """Project AI Readiness Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    ai_findings = tuple(item for item in findings if _is_ai_readiness_finding(item))
    ai_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in ai_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    ai_recs = tuple(
        item
        for item in recommendations
        if _is_ai_readiness_recommendation(item, ai_finding_ids)
    )

    finding_links = _finding_links(ai_findings)
    recommendation_links = _recommendation_links(
        ai_recs, report, ai_finding_ids
    )
    signal_groups = _signal_groups(report, ai_findings)
    coverage_rows = _coverage_rows(report)
    overview = _overview(
        report,
        finding_links=finding_links,
        recommendation_links=recommendation_links,
        signal_groups=signal_groups,
    )
    limitations = _limitations(report, finding_links=finding_links)
    confidence, confidence_label = _confidence(
        report=report,
        finding_links=finding_links,
        limitations=limitations,
    )

    inventory_count = int(report.inventory_summary.finding_count or 0)
    if finding_links:
        finding_count = len(finding_links)
        empty_message = None
    else:
        finding_count = inventory_count
        empty_message = _EMPTY_FINDINGS_MESSAGE if inventory_count == 0 else None

    return AiReadinessIntelligenceSection(
        status=report.status,
        status_label=report.status_label,
        status_summary=_safe_status_summary(report.status_summary),
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        signal_groups=signal_groups,
        findings=finding_links,
        recommendations=recommendation_links,
        coverage_rows=coverage_rows,
        limitations=limitations,
        finding_count=finding_count,
        recommendation_count=len(recommendation_links),
        empty_findings_message=empty_message,
    )


def scrub_soft_ai_readiness_claims(text: str, *, fallback: str) -> str:
    """Replace soft AI-readiness claims with a safe observational fallback."""

    if not text or not str(text).strip():
        return fallback
    if _contains_soft_claim(text):
        return fallback
    return str(text).strip()


def _contains_soft_claim(text: str) -> bool:
    lowered = str(text).lower()
    # Observational "ai readiness" phrasing is allowed; neutralize before
    # substring checks so "ai ready" does not false-positive on it.
    neutralized = (
        lowered.replace("does not establish that the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("do not establish ai readiness", "")
        .replace("absence of findings does not establish ai readiness", "")
        .replace("readiness scores are not measured", "")
        .replace("no numeric ai enablement score", "")
        .replace("no numeric ai-readiness score", "")
        .replace("ai-readiness", "")
        .replace("ai readiness", "")
        .replace("not ai ready", "")
    )
    return any(fragment in neutralized for fragment in _SOFT_CLAIM_FRAGMENTS)


def _is_ai_readiness_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    return (
        category == "ai_readiness"
        or rule_id.startswith("ai_readiness.")
        or rule_id.startswith("ai-readiness.")
    )


def _is_ai_readiness_recommendation(
    item: Any,
    ai_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category == "ai_readiness":
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(ai_finding_ids)


def _safe_status_summary(text: str) -> str:
    return scrub_soft_ai_readiness_claims(text, fallback=_SAFE_STATUS_SUMMARY)


def _finding_links(findings: Sequence[Any]) -> tuple[AiReadinessFindingLink, ...]:
    if not findings:
        return ()
    rows = [
        AiReadinessFindingLink(
            finding_id=item.finding_id,
            title=item.title,
            severity=item.severity,
            confidence=_finding_confidence_label(item),
            evidence_ids=_evidence_ids(item),
            recommendation_ids=tuple(
                getattr(item, "driven_recommendation_ids", ()) or ()
            ),
            path=_finding_path(item),
            rule_id=str(getattr(item, "rule_id", "") or "ai_readiness.unknown"),
            evidence_completeness=(
                str(getattr(item, "evidence_completeness", "") or "").strip()
                or None
            ),
        )
        for item in findings
    ]
    rows.sort(
        key=lambda row: (
            row.severity.lower(),
            row.title.lower(),
            row.finding_id,
        )
    )
    return tuple(rows)


def _finding_confidence_label(item: Any) -> str:
    direct = (getattr(item, "confidence", None) or "").strip().lower()
    if direct in _CONFIDENCE_RANK:
        if direct == "medium":
            return "moderate"
        if direct == "low":
            return "limited"
        return direct
    completeness = (getattr(item, "evidence_completeness", None) or "").strip().lower()
    if completeness in {"complete", "high"}:
        return "high"
    if completeness in {"partial", "moderate"}:
        return "moderate"
    if completeness in {"limited", "low"}:
        return "limited"
    if completeness in {"legacy", "unavailable", "unknown", ""}:
        return "unavailable"
    return "unavailable"


def _evidence_ids(item: Any) -> tuple[str, ...]:
    refs = getattr(item, "evidence_refs", None)
    if refs:
        return tuple(
            getattr(ref, "evidence_id", "")
            for ref in refs
            if getattr(ref, "evidence_id", None)
        )
    ids = getattr(item, "evidence_ids", None)
    if ids:
        return tuple(str(item_id).strip() for item_id in ids if str(item_id).strip())
    return ()


def _finding_path(item: Any) -> str | None:
    path = _safe_path(getattr(item, "path", None))
    if path:
        return path
    for ref in getattr(item, "evidence_refs", ()) or ():
        path = _safe_path(getattr(ref, "path", None))
        if path:
            return path
    for node in getattr(item, "affected_nodes", ()) or ():
        path = _safe_path(str(node))
        if path:
            return path
    return None


def _recommendation_links(
    recommendations: Sequence[Any],
    report: AiReadinessReportSection,
    ai_finding_ids: set[str],
) -> tuple[AiReadinessRecommendationLink, ...]:
    if recommendations:
        rows = [
            AiReadinessRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in ai_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        AiReadinessRecommendationLink(
            recommendation_id=item.recommendation_id,
            title=item.title,
            priority=None,
            finding_ids=tuple(item.finding_ids),
            objective=item.action or item.rationale or None,
        )
        for item in report.recommendations
    ]
    rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
    return tuple(rows)


def _signal_groups(
    report: AiReadinessReportSection,
    findings: Sequence[Any],
) -> tuple[AiReadinessSignalGroup, ...]:
    path_by_finding = {
        str(getattr(item, "finding_id", "") or ""): _finding_path(item)
        for item in findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    groups: list[AiReadinessSignalGroup] = []
    for entry in report.capability_family_summary.entries:
        if not entry.observed:
            continue
        signals = _signals_for_family(entry, path_by_finding=path_by_finding)
        if not signals:
            continue
        family = _normalize_family(entry.family_id)
        groups.append(
            AiReadinessSignalGroup(
                group_id=family,
                title=_FAMILY_TITLES.get(family, _FAMILY_TITLES["other"]),
                signals=signals,
            )
        )
    return tuple(groups)


def _signals_for_family(
    entry: AiReadinessReportCapabilityFamilyEntry,
    *,
    path_by_finding: dict[str, str | None],
) -> tuple[AiReadinessSignalRow, ...]:
    family = _normalize_family(entry.family_id)
    note = _FAMILY_NOTES.get(family, _FAMILY_NOTES["other"])
    finding_ids = tuple(entry.finding_ids)
    first_finding_id = finding_ids[0] if finding_ids else None
    path = path_by_finding.get(first_finding_id) if first_finding_id else None

    if entry.signals:
        rows = [
            AiReadinessSignalRow(
                label=(
                    "Repository-observable AI-enablement signals associated "
                    f"with {signal} were detected."
                ),
                family=family,  # type: ignore[arg-type]
                path=path,
                evidence_ids=(),
                finding_id=first_finding_id,
                note=note,
                limitations=(),
            )
            for signal in entry.signals
        ]
        return tuple(rows)

    family_label = family.replace("_", " ")
    return (
        AiReadinessSignalRow(
            label=(
                "Repository-observable AI-enablement signals associated "
                f"with {family_label} were detected."
            ),
            family=family,  # type: ignore[arg-type]
            path=path,
            evidence_ids=(),
            finding_id=first_finding_id,
            note=note,
            limitations=(),
        ),
    )


def _normalize_family(family_id: str) -> AiReadinessSignalFamily:
    key = (family_id or "").strip().lower()
    if key in _KNOWN_FAMILIES or key == "other":
        return key  # type: ignore[return-value]
    return "other"


def _overview(
    report: AiReadinessReportSection,
    *,
    finding_links: Sequence[AiReadinessFindingLink],
    recommendation_links: Sequence[AiReadinessRecommendationLink],
    signal_groups: Sequence[AiReadinessSignalGroup],
) -> tuple[AiReadinessOverviewFact, ...]:
    families = report.capability_family_summary
    cov = report.coverage_summary
    inventory_count = int(report.inventory_summary.finding_count or 0)
    finding_count = len(finding_links) if finding_links else inventory_count
    facts: list[AiReadinessOverviewFact] = [
        AiReadinessOverviewFact(label="Assessment status", value=report.status_label),
        AiReadinessOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Repository-observable signals only",
        ),
        AiReadinessOverviewFact(
            label="AI readiness findings",
            value=str(finding_count),
            note="Zero findings do not establish AI readiness",
        ),
        AiReadinessOverviewFact(
            label="AI readiness recommendations",
            value=str(len(recommendation_links)),
        ),
        AiReadinessOverviewFact(
            label="Capability families observed",
            value=f"{families.families_observed} / {families.families_total}",
            note="Signals are repository-observable only",
        ),
    ]
    if cov.evidence_status:
        facts.append(
            AiReadinessOverviewFact(
                label="Evidence status",
                value=cov.evidence_status,
            )
        )
    if signal_groups:
        signal_count = sum(len(group.signals) for group in signal_groups)
        facts.append(
            AiReadinessOverviewFact(
                label="Observable signal rows",
                value=str(signal_count),
                note="Detected integrations do not prove production use",
            )
        )
    return tuple(facts)


def _coverage_rows(
    report: AiReadinessReportSection,
) -> tuple[AiReadinessCoverageRow, ...]:
    cov = report.coverage_summary
    rows: list[AiReadinessCoverageRow] = []
    if cov.evidence_status:
        status = "available"
        if cov.evidence_status.lower() in {
            "partially_succeeded",
            "partial",
            "insufficient",
        }:
            status = "partial"
        rows.append(
            AiReadinessCoverageRow(
                label="Evidence status",
                status=status,
                display=cov.evidence_status,
                note=None,
            )
        )
    if cov.evidence_pipeline:
        rows.append(
            AiReadinessCoverageRow(
                label="Evidence pipeline",
                status="available",
                display=cov.evidence_pipeline,
                note=None,
            )
        )
    for area in cov.areas:
        rows.append(_coverage_area_row(area))
    if cov.note:
        rows.append(
            AiReadinessCoverageRow(
                label="Coverage note",
                status="available",
                display=cov.note,
                note=None,
            )
        )
    rows.sort(key=lambda row: row.label.lower())
    return tuple(rows)


def _coverage_area_row(area: AiReadinessReportCoverageAreaView) -> AiReadinessCoverageRow:
    label = area.area_id.replace("_", " ").replace("-", " ").strip() or area.area_id
    display_parts: list[str] = []
    if area.numerator is not None or area.denominator is not None:
        num = "—" if area.numerator is None else str(area.numerator)
        den = "—" if area.denominator is None else str(area.denominator)
        display_parts.append(f"{num} / {den}")
    if area.maturity and area.maturity != "unknown":
        display_parts.append(f"maturity: {area.maturity}")
    display = "; ".join(display_parts) if display_parts else area.status
    note = None
    if area.status.lower() in {"partial", "limited", "insufficient"}:
        note = "Coverage describes assessed capability areas only"
    return AiReadinessCoverageRow(
        label=label.title() if label.islower() or "_" in area.area_id else label,
        status=area.status,
        display=display,
        note=note,
    )


def _limitations(
    report: AiReadinessReportSection,
    *,
    finding_links: Sequence[AiReadinessFindingLink],
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    for item in report.limitations:
        summary = (item.summary or "").strip()
        if not summary:
            continue
        lowered = summary.lower()
        if any(fragment in lowered for fragment in _SOFT_CLAIM_FRAGMENTS):
            continue
        if "phase " in lowered:
            continue
        notes.append(summary)
    if report.status in {"insufficient_evidence", "partially_succeeded"}:
        notes.append("AI readiness coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("AI readiness analysis did not produce a complete assessment.")
    if not finding_links and report.inventory_summary.finding_count == 0:
        notes.append(
            "No AI readiness findings were produced within the assessed "
            "repository scope."
        )
    # Soft-scrub legacy posture / none-detected if they carry soft claims.
    posture = (report.overall_posture_summary or "").strip()
    if posture and _contains_soft_claim(posture):
        notes.append(_SAFE_POSTURE_SUMMARY)
    none_detected = (report.inventory_summary.none_detected_statement or "").strip()
    if none_detected and _contains_soft_claim(none_detected):
        notes.append(_EMPTY_FINDINGS_MESSAGE)

    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return tuple(out)


def _confidence(
    *,
    report: AiReadinessReportSection,
    finding_links: Sequence[AiReadinessFindingLink],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))

    if report.status in {"insufficient_evidence", "partially_succeeded", "failed"}:
        ranks.append(1)
    if limitations and not finding_links:
        ranks.append(0)
    if report.capability_family_summary.families_observed == 0:
        ranks.append(1)

    if not ranks:
        return "unavailable", "Confidence unavailable"
    weakest = min(ranks)
    if weakest >= 3:
        return "high", "High confidence"
    if weakest == 2:
        return "moderate", "Moderate confidence"
    if weakest == 1:
        return "limited", "Limited confidence"
    return "unavailable", "Confidence unavailable"


def _safe_token(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("/") or text.startswith("file:"):
        return None
    if ".." in text.split("/"):
        return None
    if text.startswith("<") and text.endswith(">"):
        return None
    lowered = text.lower()
    for fragment in _UNSAFE_PATH_FRAGMENTS:
        if fragment in lowered:
            return None
    return text


def _safe_path(path: str | None) -> str | None:
    return _safe_token(path)
