"""Build Dependency Intelligence from existing report + findings (Epic 3 Slice 3.5).

Do NOT import from codestrata.reporting.html_v2 (circular import). Duck-type
findings/recommendations with Any + getattr.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS
from codestrata.reporting.dependency.intelligence_models import (
    DependencyCoverageRow,
    DependencyEcosystemRow,
    DependencyFindingLink,
    DependencyIntelligenceSection,
    DependencyManifestRow,
    DependencyOverviewFact,
    DependencyRecommendationLink,
)
from codestrata.reporting.dependency.models import DependencyReportSection

_BASE_LIMITATIONS = (
    "Only declaration hygiene was assessed for supported ecosystems.",
    "No registry lookups, CVE analysis, license validation, or dependency "
    "freshness checks were performed.",
    "Supported ecosystems and package managers only; unsupported manifests "
    "may be omitted.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "healthy",
    "secure dependency",
    "secure supply",
    "safe supply chain",
    "modern dependency",
    "modern stack",
    "no dependency risk",
    "no dependency risks",
    "cve",
    "license compliance",
    "license validation",
    "freshness",
    "up to date",
    "outdated dependency",
)

_UNSUPPORTED_FINDING_FRAGMENTS = (
    "cve",
    "license",
    "freshness",
    "outdated",
    "vulnerable",
    "vulnerability",
    "vulnerabilities",
    "abandoned",
)

_EMPTY_FINDINGS_MESSAGE = (
    "No dependency hygiene findings were produced within the assessed scope. "
    "Only declaration hygiene was assessed. Zero findings do not mean a "
    "healthy or secure dependency posture."
)

_SAFE_STATUS_SUMMARY = (
    "Dependency assessment completed using declaration-hygiene evidence. "
    "Zero findings do not certify a healthy or secure dependency posture."
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

_HYGIENE_RULE_IDS = frozenset(HYGIENE_RULE_IDS)


def build_dependency_intelligence(
    report: DependencyReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> DependencyIntelligenceSection | None:
    """Project Dependency Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    dep_findings = tuple(item for item in findings if _is_dependency_finding(item))
    dep_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in dep_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    dep_recs = tuple(
        item
        for item in recommendations
        if _is_dependency_recommendation(item, dep_finding_ids)
    )

    finding_links = _finding_links(dep_findings, report)
    recommendation_links = _recommendation_links(dep_recs, report, dep_finding_ids)
    ecosystems = _ecosystems(report)
    manifests = _manifests(report)
    coverage_rows = _coverage_rows(report)
    overview = _overview(
        report,
        finding_links=finding_links,
        recommendation_links=recommendation_links,
        ecosystems=ecosystems,
        manifests=manifests,
    )
    limitations = _limitations(report, finding_links=finding_links)
    confidence, confidence_label = _confidence(
        report=report,
        finding_links=finding_links,
        limitations=limitations,
    )
    empty_message = None if finding_links else _EMPTY_FINDINGS_MESSAGE

    return DependencyIntelligenceSection(
        status=report.status,
        status_label=report.status_label,
        status_summary=_safe_status_summary(report.status_summary),
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        ecosystems=ecosystems,
        manifests=manifests,
        findings=finding_links,
        recommendations=recommendation_links,
        coverage_rows=coverage_rows,
        limitations=limitations,
        finding_count=len(finding_links),
        recommendation_count=len(recommendation_links),
        empty_findings_message=empty_message,
    )


def _is_dependency_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    title = (getattr(item, "title", None) or "").strip().lower()
    if not (category == "dependency" or rule_id.startswith("dependency.")):
        return False
    haystack = f"{rule_id} {title}"
    if any(fragment in haystack for fragment in _UNSUPPORTED_FINDING_FRAGMENTS):
        return False
    if rule_id.startswith("dependency.") and rule_id not in _HYGIENE_RULE_IDS:
        return False
    return True


def _is_dependency_recommendation(
    item: Any,
    dependency_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category == "dependency":
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(dependency_finding_ids)


def _safe_status_summary(text: str) -> str:
    lowered = text.lower()
    for fragment in _SOFT_CLAIM_FRAGMENTS:
        if fragment in lowered:
            return _SAFE_STATUS_SUMMARY
    return text


def _finding_links(
    findings: Sequence[Any],
    report: DependencyReportSection,
) -> tuple[DependencyFindingLink, ...]:
    if findings:
        rows = [
            DependencyFindingLink(
                finding_id=item.finding_id,
                title=item.title,
                severity=item.severity,
                confidence=_finding_confidence_label(item),
                evidence_ids=_evidence_ids(item),
                recommendation_ids=tuple(
                    getattr(item, "driven_recommendation_ids", ()) or ()
                ),
                path=_finding_path(item),
                ecosystem=_finding_ecosystem(item),
                rule_id=str(getattr(item, "rule_id", "") or "dependency.unknown"),
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

    # Prefer production hygiene findings from the report when HTML findings empty.
    report_findings = tuple(report.production_health.findings)
    if not report_findings:
        return ()
    rows = [
        DependencyFindingLink(
            finding_id=item.finding_id,
            title=item.title,
            severity=item.severity,
            confidence=item.confidence,
            evidence_ids=tuple(item.evidence_ids),
            recommendation_ids=(),
            path=_safe_path(item.path),
            ecosystem=_safe_token(item.ecosystem),
            rule_id=item.rule_id,
        )
        for item in report_findings
        if _is_dependency_finding(item)
    ]
    rows.sort(
        key=lambda row: (row.severity.lower(), row.title.lower(), row.finding_id)
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


def _finding_ecosystem(item: Any) -> str | None:
    ecosystem = _safe_token(getattr(item, "ecosystem", None))
    if ecosystem:
        return ecosystem
    return None


def _recommendation_links(
    recommendations: Sequence[Any],
    report: DependencyReportSection,
    dependency_finding_ids: set[str],
) -> tuple[DependencyRecommendationLink, ...]:
    if recommendations:
        rows = [
            DependencyRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in dependency_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        DependencyRecommendationLink(
            recommendation_id=item.recommendation_id,
            title=item.title,
            priority=None,
            finding_ids=(),
            objective=item.action or item.rationale or None,
        )
        for item in report.recommendations
    ]
    rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
    return tuple(rows)


def _ecosystems(
    report: DependencyReportSection,
) -> tuple[DependencyEcosystemRow, ...]:
    hotspot_counts: Counter[str] = Counter()
    for hotspot in report.manifest_hotspots:
        name = (hotspot.ecosystem or "").strip()
        if name:
            hotspot_counts[name.lower()] += 1

    landscape_decls: dict[str, int] = {}
    for item in report.landscape:
        key = (item.key or "").strip()
        group = (item.group or "").strip().lower()
        if group == "ecosystem" or key.startswith("ecosystem:"):
            name = key.removeprefix("ecosystem:").strip() or item.label
            name = name.removeprefix("Ecosystem:").strip() or name
            if item.count > 0:
                landscape_decls[name.lower()] = item.count

    names = sorted(
        {*_normalized_detected_names(landscape_decls), *hotspot_counts.keys()}
    )
    if not names:
        return ()

    parse_status = _aggregate_parse_status(report)
    version_availability = _version_availability(report)

    rows: list[DependencyEcosystemRow] = []
    for name_key in names:
        display_name = _display_ecosystem_name(name_key, report)
        decl_count = landscape_decls.get(name_key)
        if decl_count is None and name_key not in hotspot_counts:
            continue
        if (decl_count or 0) <= 0 and hotspot_counts.get(name_key, 0) <= 0:
            continue
        rows.append(
            DependencyEcosystemRow(
                name=display_name,
                manifest_count=hotspot_counts.get(name_key, 0),
                declaration_count=decl_count,
                parse_status=parse_status,
                version_availability=version_availability,
                note=None,
            )
        )
    rows.sort(key=lambda row: row.name.lower())
    return tuple(rows)


def _normalized_detected_names(landscape_decls: dict[str, int]) -> set[str]:
    return {name for name, count in landscape_decls.items() if count > 0}


def _display_ecosystem_name(name_key: str, report: DependencyReportSection) -> str:
    for item in report.landscape:
        key = (item.key or "").strip()
        group = (item.group or "").strip().lower()
        if group == "ecosystem" or key.startswith("ecosystem:"):
            raw = key.removeprefix("ecosystem:").strip()
            if raw.lower() == name_key:
                return raw
            label = item.label.removeprefix("Ecosystem:").strip()
            if label.lower() == name_key:
                return label
    for hotspot in report.manifest_hotspots:
        if (hotspot.ecosystem or "").strip().lower() == name_key:
            return hotspot.ecosystem
    return name_key


def _aggregate_parse_status(report: DependencyReportSection) -> str | None:
    cov = report.coverage
    if cov.manifests_failed > 0:
        return "failed"
    if cov.manifests_partially_parsed > 0:
        return "partially_parsed"
    if cov.manifests_parsed > 0:
        return "parsed"
    if cov.manifests_discovered > 0:
        return "discovered"
    return None


def _version_availability(report: DependencyReportSection) -> str | None:
    for item in report.landscape:
        key = (item.key or "").strip().lower()
        if key.startswith("version_resolution:") and item.count > 0:
            return key.removeprefix("version_resolution:")
    return None


def _manifests(
    report: DependencyReportSection,
) -> tuple[DependencyManifestRow, ...]:
    rows: list[DependencyManifestRow] = []
    for hotspot in report.manifest_hotspots:
        path = _safe_path(hotspot.path)
        if not path:
            continue
        parse_status = None
        if hotspot.diagnostics_count > 0:
            parse_status = "partial"
        rows.append(
            DependencyManifestRow(
                path=path,
                ecosystem=hotspot.ecosystem,
                manifest_type=hotspot.manifest_type,
                parse_status=parse_status,
                limitations=(),
                finding_count=hotspot.hygiene_finding_count,
            )
        )
    rows.sort(key=lambda row: (row.ecosystem.lower(), row.path.lower()))
    return tuple(rows)


def _overview(
    report: DependencyReportSection,
    *,
    finding_links: Sequence[DependencyFindingLink],
    recommendation_links: Sequence[DependencyRecommendationLink],
    ecosystems: Sequence[DependencyEcosystemRow],
    manifests: Sequence[DependencyManifestRow],
) -> tuple[DependencyOverviewFact, ...]:
    by_key = {item.key: item for item in report.landscape}
    cov = report.coverage
    facts: list[DependencyOverviewFact] = [
        DependencyOverviewFact(label="Assessment status", value=report.status_label),
        DependencyOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Declaration hygiene only",
        ),
        DependencyOverviewFact(
            label="Dependency hygiene findings",
            value=str(len(finding_links)),
            note="Zero findings do not mean a healthy or secure dependency posture",
        ),
        DependencyOverviewFact(
            label="Dependency recommendations",
            value=str(len(recommendation_links)),
        ),
        DependencyOverviewFact(
            label="Detected ecosystems",
            value=str(len(ecosystems)),
        ),
        DependencyOverviewFact(
            label="Manifest inventory",
            value=str(len(manifests)),
        ),
    ]
    for key, label in (
        ("declarations_collected", "Declarations collected"),
        ("manifests_supported", "Supported manifests"),
        ("production_active", "Production active dependencies"),
    ):
        item = by_key.get(key)
        if item is not None:
            facts.append(
                DependencyOverviewFact(label=label, value=str(item.count))
            )
    if cov.manifests_discovered or cov.manifests_parsed or cov.manifests_failed:
        facts.append(
            DependencyOverviewFact(
                label="Manifests discovered",
                value=str(cov.manifests_discovered),
            )
        )
        facts.append(
            DependencyOverviewFact(
                label="Manifests parsed",
                value=str(cov.manifests_parsed),
            )
        )
    return tuple(facts)


def _coverage_rows(
    report: DependencyReportSection,
) -> tuple[DependencyCoverageRow, ...]:
    cov = report.coverage
    specs: tuple[tuple[str, int, str | None], ...] = (
        ("Manifests discovered", cov.manifests_discovered, None),
        ("Manifests supported", cov.manifests_supported, None),
        ("Manifests parsed", cov.manifests_parsed, None),
        (
            "Manifests partially parsed",
            cov.manifests_partially_parsed,
            "Partial parse does not imply healthy dependencies",
        ),
        (
            "Manifests failed",
            cov.manifests_failed,
            "Parse failures limit declaration hygiene coverage",
        ),
        ("Production parse failures", cov.production_parse_failures, None),
        ("Test/fixture parse failures", cov.test_fixture_parse_failures, None),
        ("Unsupported constructs", cov.unsupported_construct_count, None),
        ("Proven unresolved versions", cov.proven_unresolved_count, None),
        ("Unsupported resolutions", cov.unsupported_resolution_count, None),
        (
            "Diagnostics",
            cov.diagnostic_total,
            cov.note if cov.note else None,
        ),
    )
    rows: list[DependencyCoverageRow] = []
    for label, value, note in specs:
        if value <= 0 and label not in {
            "Manifests discovered",
            "Manifests supported",
            "Manifests parsed",
        }:
            continue
        status = "available"
        if label == "Manifests failed" and value > 0:
            status = "limited"
        elif label == "Manifests partially parsed" and value > 0:
            status = "partial"
        rows.append(
            DependencyCoverageRow(
                label=label,
                status=status,
                display=str(value),
                note=note,
            )
        )
    rows.sort(key=lambda row: row.label.lower())
    return tuple(rows)


def _limitations(
    report: DependencyReportSection,
    *,
    finding_links: Sequence[DependencyFindingLink],
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
        notes.append("Dependency coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("Dependency analysis did not produce a complete assessment.")
    if report.coverage.manifests_failed > 0 or report.coverage.manifests_partially_parsed > 0:
        notes.append(
            "Some manifests failed or partially parsed; declaration hygiene "
            "coverage may be incomplete."
        )
    if not finding_links:
        notes.append(
            "No dependency hygiene findings were produced within the assessed scope."
        )
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
    report: DependencyReportSection,
    finding_links: Sequence[DependencyFindingLink],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))

    cov = report.coverage
    if cov.manifests_failed > 0 or cov.manifests_partially_parsed > 0:
        ranks.append(1)
    if cov.production_parse_failures > 0:
        ranks.append(1)

    if report.status in {"insufficient_evidence", "partially_succeeded", "failed"}:
        ranks.append(1)
    if limitations and not finding_links:
        ranks.append(0)

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
