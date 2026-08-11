"""Build Cloud Readiness Intelligence from existing report + findings (Epic 3 Slice 3.7).

Do NOT import from codestrata.reporting.html_v2 (circular import). Duck-type
findings/recommendations with Any + getattr.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporting.cloud.intelligence_models import (
    CloudCoverageRow,
    CloudFindingLink,
    CloudIntelligenceSection,
    CloudOverviewFact,
    CloudRecommendationLink,
    CloudSignalFamily,
    CloudSignalGroup,
    CloudSignalRow,
)
from codestrata.reporting.cloud.models import (
    CloudReportCoverageAreaView,
    CloudReportSection,
    CloudReportTechnologyFamilyEntry,
)

_BASE_LIMITATIONS = (
    "Repository evidence only.",
    "No cloud-provider API calls.",
    "No live infrastructure inspection.",
    "No deployed runtime state.",
    "No network or identity posture inspection.",
    "No cost analysis.",
    "No resilience or availability validation.",
    "No runtime scalability assessment.",
    "Externalized configuration not fully assessed.",
    "Statelessness not fully assessed.",
    "No numeric cloud-readiness score.",
    "Detected declarations do not prove successful deployment.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "cloud ready",
    "is cloud ready",
    "are cloud ready",
    "migration ready",
    "cloud-native",
    "cloud native",
    "production ready",
    "highly available",
    "scalable",
    "resilient",
    "cost optimized",
    "secure cloud",
    "operationally mature",
    "no cloud risks",
    "no cloud issues",
    "fully portable",
    "runs on aws",
    "runs on azure",
    "runs on gcp",
    "deployed to",
    "migrate to",
)

_EMPTY_FINDINGS_MESSAGE = (
    "No cloud findings were produced within the assessed repository scope. "
    "Live cloud infrastructure and runtime posture were not assessed. Absence "
    "of findings does not establish cloud readiness."
)

_SAFE_STATUS_SUMMARY = (
    "Cloud assessment completed using repository-observable evidence. "
    "Zero findings do not establish cloud readiness. Detected declarations "
    "do not prove successful deployment."
)

_SAFE_POSTURE_SUMMARY = (
    "Repository cloud signals were assessed from static evidence only. "
    "This does not establish cloud readiness, migration readiness, or a "
    "live deployment posture."
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
    "platforms": "Platforms and runtime signals",
    "containers": "Containers",
    "orchestration": "Orchestration",
    "iac": "Infrastructure as code",
    "serverless": "Serverless",
    "managed_services": "Managed services",
    "deployment_pipelines": "Deployment pipelines",
    "other": "Other cloud signals",
}

_FAMILY_NOTES: dict[str, str] = {
    "platforms": (
        "Detected platform declarations do not prove a live deployment."
    ),
    "containers": (
        "Container declarations do not establish cloud readiness."
    ),
    "orchestration": (
        "Orchestration declarations do not prove successful deployment."
    ),
    "iac": (
        "Infrastructure-as-code declarations do not establish quality or "
        "drift posture."
    ),
    "serverless": (
        "Serverless declarations do not prove a production resource."
    ),
    "managed_services": (
        "Managed-service declarations do not prove a live deployment."
    ),
    "deployment_pipelines": (
        "Pipeline declarations do not prove successful delivery."
    ),
    "other": "Detected declarations do not prove successful deployment.",
}

_KNOWN_FAMILIES = frozenset(_FAMILY_TITLES) - {"other"}


def build_cloud_intelligence(
    report: CloudReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> CloudIntelligenceSection | None:
    """Project Cloud Readiness Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    cloud_findings = tuple(item for item in findings if _is_cloud_finding(item))
    cloud_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in cloud_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    cloud_recs = tuple(
        item
        for item in recommendations
        if _is_cloud_recommendation(item, cloud_finding_ids)
    )

    finding_links = _finding_links(cloud_findings)
    recommendation_links = _recommendation_links(
        cloud_recs, report, cloud_finding_ids
    )
    signal_groups = _signal_groups(report, cloud_findings)
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

    return CloudIntelligenceSection(
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


def scrub_soft_cloud_claims(text: str, *, fallback: str) -> str:
    """Replace soft cloud-readiness claims with a safe observational fallback."""

    if not text or not str(text).strip():
        return fallback
    if _contains_soft_claim(text):
        return fallback
    return str(text).strip()


def _contains_soft_claim(text: str) -> bool:
    lowered = str(text).lower()
    # Observational "cloud readiness" phrasing is allowed; neutralize before
    # substring checks so "cloud ready" does not false-positive on it.
    neutralized = (
        lowered.replace("does not establish cloud readiness", "")
        .replace("do not establish cloud readiness", "")
        .replace("cloud readiness", "")
        .replace("not cloud ready", "")
    )
    return any(fragment in neutralized for fragment in _SOFT_CLAIM_FRAGMENTS)


def _is_cloud_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    return category in {"cloud", "cloud_readiness"} or rule_id.startswith("cloud.")


def _is_cloud_recommendation(
    item: Any,
    cloud_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category in {"cloud", "cloud_readiness"}:
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(cloud_finding_ids)


def _safe_status_summary(text: str) -> str:
    return scrub_soft_cloud_claims(text, fallback=_SAFE_STATUS_SUMMARY)


def _finding_links(findings: Sequence[Any]) -> tuple[CloudFindingLink, ...]:
    if not findings:
        return ()
    rows = [
        CloudFindingLink(
            finding_id=item.finding_id,
            title=item.title,
            severity=item.severity,
            confidence=_finding_confidence_label(item),
            evidence_ids=_evidence_ids(item),
            recommendation_ids=tuple(
                getattr(item, "driven_recommendation_ids", ()) or ()
            ),
            path=_finding_path(item),
            rule_id=str(getattr(item, "rule_id", "") or "cloud.unknown"),
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
    report: CloudReportSection,
    cloud_finding_ids: set[str],
) -> tuple[CloudRecommendationLink, ...]:
    if recommendations:
        rows = [
            CloudRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in cloud_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        CloudRecommendationLink(
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
    report: CloudReportSection,
    findings: Sequence[Any],
) -> tuple[CloudSignalGroup, ...]:
    path_by_finding = {
        str(getattr(item, "finding_id", "") or ""): _finding_path(item)
        for item in findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    groups: list[CloudSignalGroup] = []
    for entry in report.technology_family_summary.entries:
        if not entry.observed:
            continue
        signals = _signals_for_family(entry, path_by_finding=path_by_finding)
        if not signals:
            continue
        family = _normalize_family(entry.family_id)
        groups.append(
            CloudSignalGroup(
                group_id=family,
                title=_FAMILY_TITLES.get(family, _FAMILY_TITLES["other"]),
                signals=signals,
            )
        )
    return tuple(groups)


def _signals_for_family(
    entry: CloudReportTechnologyFamilyEntry,
    *,
    path_by_finding: dict[str, str | None],
) -> tuple[CloudSignalRow, ...]:
    family = _normalize_family(entry.family_id)
    note = _FAMILY_NOTES.get(family, _FAMILY_NOTES["other"])
    finding_ids = tuple(entry.finding_ids)
    first_finding_id = finding_ids[0] if finding_ids else None
    path = path_by_finding.get(first_finding_id) if first_finding_id else None

    if entry.technologies:
        rows = [
            CloudSignalRow(
                label=(
                    f"Repository signals associated with {tech} were detected."
                ),
                family=family,  # type: ignore[arg-type]
                path=path,
                evidence_ids=(),
                finding_id=first_finding_id,
                note=note,
                limitations=(),
            )
            for tech in entry.technologies
        ]
        return tuple(rows)

    family_label = family.replace("_", " ")
    return (
        CloudSignalRow(
            label=(
                f"Repository signals associated with {family_label} "
                "were detected."
            ),
            family=family,  # type: ignore[arg-type]
            path=path,
            evidence_ids=(),
            finding_id=first_finding_id,
            note=note,
            limitations=(),
        ),
    )


def _normalize_family(family_id: str) -> CloudSignalFamily:
    key = (family_id or "").strip().lower()
    if key in _KNOWN_FAMILIES or key == "other":
        return key  # type: ignore[return-value]
    return "other"


def _overview(
    report: CloudReportSection,
    *,
    finding_links: Sequence[CloudFindingLink],
    recommendation_links: Sequence[CloudRecommendationLink],
    signal_groups: Sequence[CloudSignalGroup],
) -> tuple[CloudOverviewFact, ...]:
    families = report.technology_family_summary
    cov = report.coverage_summary
    inventory_count = int(report.inventory_summary.finding_count or 0)
    finding_count = len(finding_links) if finding_links else inventory_count
    facts: list[CloudOverviewFact] = [
        CloudOverviewFact(label="Assessment status", value=report.status_label),
        CloudOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Repository-observable signals only",
        ),
        CloudOverviewFact(
            label="Cloud findings",
            value=str(finding_count),
            note="Zero findings do not establish cloud readiness",
        ),
        CloudOverviewFact(
            label="Cloud recommendations",
            value=str(len(recommendation_links)),
        ),
        CloudOverviewFact(
            label="Technology families observed",
            value=f"{families.families_observed} / {families.families_total}",
            note="Signals are repository-observable only",
        ),
    ]
    if cov.evidence_status:
        facts.append(
            CloudOverviewFact(
                label="Evidence status",
                value=cov.evidence_status,
            )
        )
    if signal_groups:
        signal_count = sum(len(group.signals) for group in signal_groups)
        facts.append(
            CloudOverviewFact(
                label="Observable signal rows",
                value=str(signal_count),
                note="Detected declarations do not prove successful deployment",
            )
        )
    return tuple(facts)


def _coverage_rows(
    report: CloudReportSection,
) -> tuple[CloudCoverageRow, ...]:
    cov = report.coverage_summary
    rows: list[CloudCoverageRow] = []
    if cov.evidence_status:
        status = "available"
        if cov.evidence_status.lower() in {
            "partially_succeeded",
            "partial",
            "insufficient",
        }:
            status = "partial"
        rows.append(
            CloudCoverageRow(
                label="Evidence status",
                status=status,
                display=cov.evidence_status,
                note=None,
            )
        )
    if cov.evidence_pipeline:
        rows.append(
            CloudCoverageRow(
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
            CloudCoverageRow(
                label="Coverage note",
                status="available",
                display=cov.note,
                note=None,
            )
        )
    rows.sort(key=lambda row: row.label.lower())
    return tuple(rows)


def _coverage_area_row(area: CloudReportCoverageAreaView) -> CloudCoverageRow:
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
    return CloudCoverageRow(
        label=label.title() if label.islower() or "_" in area.area_id else label,
        status=area.status,
        display=display,
        note=note,
    )


def _limitations(
    report: CloudReportSection,
    *,
    finding_links: Sequence[CloudFindingLink],
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
        notes.append("Cloud coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("Cloud analysis did not produce a complete assessment.")
    if not finding_links and report.inventory_summary.finding_count == 0:
        notes.append(
            "No cloud findings were produced within the assessed repository scope."
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
    report: CloudReportSection,
    finding_links: Sequence[CloudFindingLink],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))

    if report.status in {"insufficient_evidence", "partially_succeeded", "failed"}:
        ranks.append(1)
    if limitations and not finding_links:
        ranks.append(0)
    if report.technology_family_summary.families_observed == 0:
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
    return text


def _safe_path(path: str | None) -> str | None:
    return _safe_token(path)
