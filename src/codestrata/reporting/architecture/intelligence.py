"""Build Architecture Intelligence from existing report + findings (Epic 3 Slice 3.3)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporting.architecture.intelligence_models import (
    ArchitectureConclusionLink,
    ArchitectureCoverageRow,
    ArchitectureFindingLink,
    ArchitectureGraphEvidenceRow,
    ArchitectureIntelligenceSection,
    ArchitectureInventoryItem,
    ArchitectureMeasurementRow,
    ArchitectureOverviewFact,
    ArchitectureRecommendationLink,
)
from codestrata.reporting.architecture.models import ArchitectureReportSection

_BASE_LIMITATIONS = (
    "Architecture Intelligence reflects static repository structure only.",
    "Runtime architecture, deployed topology, and service behavior were not assessed.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "architecture is healthy",
    "well-architected",
    "microservices architecture",
    "highly scalable",
    "loosely coupled",
    "production-ready architecture",
    "no architecture risk",
    "no significant architecture risk",
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


def build_architecture_intelligence(
    report: ArchitectureReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> ArchitectureIntelligenceSection | None:
    """Project Architecture Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    arch_findings = tuple(
        item for item in findings if _is_architecture_finding(item)
    )
    arch_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in arch_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    arch_recs = tuple(
        item
        for item in recommendations
        if _is_architecture_recommendation(item, arch_finding_ids)
    )

    # Prefer canonical customer findings; fall back to report finding summaries.
    finding_links = _finding_links(arch_findings, report)
    recommendation_links = _recommendation_links(arch_recs, report, arch_finding_ids)
    conclusion_links = _conclusion_links(report, arch_finding_ids)
    inventory = _inventory(report, finding_links)
    overview = _overview(report, finding_links, recommendation_links, inventory)
    graph_rows = _graph_evidence(arch_findings, report)
    measurements = _measurements(arch_findings)
    coverage_rows = _coverage_rows(report)
    limitations = _limitations(report, finding_links=finding_links, graph_rows=graph_rows)
    confidence, confidence_label = _confidence(
        report=report,
        finding_links=finding_links,
        limitations=limitations,
    )
    empty_message = None
    if not finding_links:
        empty_message = (
            "No architecture findings were produced within the assessed scope. "
            "Runtime architecture was not assessed."
        )

    return ArchitectureIntelligenceSection(
        status=report.status,
        status_label=report.status_label,
        status_summary=_safe_status_summary(report.status_summary),
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        inventory_items=inventory,
        findings=finding_links,
        recommendations=recommendation_links,
        conclusions=conclusion_links,
        graph_evidence=graph_rows,
        measurements=measurements,
        coverage_rows=coverage_rows,
        limitations=limitations,
        finding_count=len(finding_links),
        recommendation_count=len(recommendation_links),
        graph_available=bool(graph_rows) or bool(report.metadata.get("graph_fingerprint")),
        empty_findings_message=empty_message,
    )


def _is_architecture_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    return category == "architecture" or rule_id.startswith("architecture.")


def _is_architecture_recommendation(
    item: Any,
    architecture_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category == "architecture":
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(architecture_finding_ids)


def _safe_status_summary(text: str) -> str:
    lowered = text.lower()
    for fragment in _SOFT_CLAIM_FRAGMENTS:
        if fragment in lowered:
            return (
                "Architecture assessment completed using static repository evidence. "
                "Zero findings do not certify a healthy architecture."
            )
    return text


def _finding_links(
    findings: Sequence[Any],
    report: ArchitectureReportSection,
) -> tuple[ArchitectureFindingLink, ...]:
    if findings:
        rows = [
            ArchitectureFindingLink(
                finding_id=item.finding_id,
                title=item.title,
                severity=item.severity,
                confidence=_finding_confidence_label(item),
                evidence_ids=tuple(
                    getattr(ref, "evidence_id", "")
                    for ref in (getattr(item, "evidence_refs", ()) or ())
                    if getattr(ref, "evidence_id", None)
                ),
                recommendation_ids=tuple(
                    getattr(item, "driven_recommendation_ids", ()) or ()
                ),
                affected_scope=_safe_scope(getattr(item, "affected_nodes", ()) or ()),
            )
            for item in findings
        ]
        rows.sort(key=lambda row: (row.severity.lower(), row.title.lower(), row.finding_id))
        return tuple(rows)

    rows = [
        ArchitectureFindingLink(
            finding_id=item.finding_id,
            title=item.title,
            severity=item.severity,
            confidence=item.confidence,
            evidence_ids=(),
            recommendation_ids=item.recommendation_ids,
            affected_scope=_safe_scope(item.affected_scope),
        )
        for item in report.findings
    ]
    rows.sort(key=lambda row: (row.severity.lower(), row.title.lower(), row.finding_id))
    return tuple(rows)


def _finding_confidence_label(item: Any) -> str:
    for ref in getattr(item, "evidence_refs", ()) or ():
        # Prefer explicit completeness signal over inventing numeric confidence.
        del ref
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


def _recommendation_links(
    recommendations: Sequence[Any],
    report: ArchitectureReportSection,
    architecture_finding_ids: set[str],
) -> tuple[ArchitectureRecommendationLink, ...]:
    if recommendations:
        rows = [
            ArchitectureRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in architecture_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        ArchitectureRecommendationLink(
            recommendation_id=item.recommendation_group_id,
            title=item.title,
            priority=None,
            finding_ids=item.source_finding_ids,
            objective=item.objective,
        )
        for item in report.recommendation_groups
    ]
    rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
    return tuple(rows)


def _conclusion_links(
    report: ArchitectureReportSection,
    architecture_finding_ids: set[str],
) -> tuple[ArchitectureConclusionLink, ...]:
    rows: list[ArchitectureConclusionLink] = []
    for item in report.conclusions:
        primary = item.primary_finding_id
        supporting_ids = [
            finding.finding_id
            for finding in report.findings
            if item.conclusion_id in finding.conclusion_ids
        ]
        if primary and primary not in supporting_ids:
            supporting_ids.insert(0, primary)
        if architecture_finding_ids:
            supporting_ids = [
                fid for fid in supporting_ids if fid in architecture_finding_ids
            ] or supporting_ids
        rows.append(
            ArchitectureConclusionLink(
                conclusion_id=item.conclusion_id,
                title=item.title,
                summary=_qualify_conclusion_text(item.summary),
                confidence=item.confidence,
                primary_finding_id=primary,
                supporting_finding_ids=tuple(supporting_ids),
                recommendation_group_ids=item.recommendation_group_ids,
                affected_scope=_safe_scope(item.affected_scope),
                severity_summary=item.severity_summary or None,
            )
        )
    rows.sort(key=lambda row: (row.title.lower(), row.conclusion_id))
    return tuple(rows)


def _qualify_conclusion_text(text: str) -> str:
    lowered = text.lower()
    for fragment in _SOFT_CLAIM_FRAGMENTS:
        if fragment in lowered:
            return (
                "Observed architecture signals are described without a healthy/ready "
                "certification. Review linked findings and evidence."
            )
    return text


def _inventory(
    report: ArchitectureReportSection,
    findings: Sequence[ArchitectureFindingLink],
) -> tuple[ArchitectureInventoryItem, ...]:
    items: dict[tuple[str, str], ArchitectureInventoryItem] = {}

    def add(name: str, kind: str, *, detail: str | None = None, source: str | None = None) -> None:
        clean = _safe_token(name)
        if not clean:
            return
        key = (clean.lower(), kind)
        if key in items:
            return
        items[key] = ArchitectureInventoryItem(
            name=clean,
            kind=kind,
            detail=detail,
            source=source,
        )

    for finding in findings:
        for scope in finding.affected_scope:
            add(scope, "observed_unit", source=finding.finding_id)
    for conclusion in report.conclusions:
        for scope in conclusion.affected_scope:
            add(scope, "observed_unit", source=conclusion.conclusion_id)
    for metric in report.key_metrics:
        key = metric.key.lower()
        if key in {"visible_findings", "conclusions", "recommendation_groups", "limitations"}:
            continue
        if "coverage" in key:
            continue
        add(metric.label, "structural_metric", detail=metric.value, source=metric.key)
    fingerprint = (report.metadata.get("graph_fingerprint") or "").strip()
    if fingerprint:
        add(
            "Architecture graph fingerprint",
            "graph_signal",
            detail="present",
            source="graph_fingerprint",
        )
    return tuple(sorted(items.values(), key=lambda item: (item.kind, item.name.lower())))


def _overview(
    report: ArchitectureReportSection,
    findings: Sequence[ArchitectureFindingLink],
    recommendations: Sequence[ArchitectureRecommendationLink],
    inventory: Sequence[ArchitectureInventoryItem],
) -> tuple[ArchitectureOverviewFact, ...]:
    facts: list[ArchitectureOverviewFact] = [
        ArchitectureOverviewFact(label="Assessment status", value=report.status_label),
        ArchitectureOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Static repository evidence only",
        ),
        ArchitectureOverviewFact(
            label="Architecture findings",
            value=str(len(findings)),
            note="Zero findings do not certify healthy architecture",
        ),
        ArchitectureOverviewFact(
            label="Architecture recommendations",
            value=str(len(recommendations)),
        ),
    ]
    if report.conclusions:
        facts.append(
            ArchitectureOverviewFact(
                label="Architecture conclusions",
                value=str(len(report.conclusions)),
            )
        )
    unit_count = sum(1 for item in inventory if item.kind == "observed_unit")
    if unit_count:
        facts.append(
            ArchitectureOverviewFact(
                label="Observed structural units",
                value=str(unit_count),
                note="Derived from finding and conclusion affected scopes",
            )
        )
    for area in report.coverage_summary:
        if area.area_id in {"extraction_coverage", "classification_coverage"}:
            facts.append(
                ArchitectureOverviewFact(
                    label=area.label,
                    value=area.display,
                    note=area.note,
                )
            )
    return tuple(facts)


def _graph_evidence(
    findings: Sequence[Any],
    report: ArchitectureReportSection,
) -> tuple[ArchitectureGraphEvidenceRow, ...]:
    rows: list[ArchitectureGraphEvidenceRow] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    for finding in findings:
        for ref in getattr(finding, "evidence_refs", ()) or ():
            node_ids = tuple(getattr(ref, "graph_node_ids", ()) or ())
            edge_ids = tuple(getattr(ref, "graph_edge_ids", ()) or ())
            relationship = getattr(ref, "graph_relationship_type", None)
            cycle_id = getattr(ref, "graph_cycle_id", None)
            reference_kind = getattr(ref, "graph_reference_kind", None)
            graph_kind = getattr(ref, "graph_kind", None)
            graph_ref_id = getattr(ref, "graph_ref_id", None)
            if not (
                graph_kind
                or graph_ref_id
                or node_ids
                or edge_ids
                or relationship
                or cycle_id
            ):
                continue
            identity_parts = []
            if node_ids:
                identity_parts.append(", ".join(node_ids[:4]))
            if edge_ids:
                identity_parts.append("edge:" + ", ".join(edge_ids[:2]))
            if not identity_parts and relationship:
                identity_parts.append(str(relationship))
            symbolic = getattr(ref, "symbolic_reference", None)
            if not identity_parts and symbolic:
                identity_parts.append(symbolic)
            if not identity_parts and graph_ref_id:
                identity_parts.append(graph_ref_id)
            identity = _safe_token(" · ".join(identity_parts)) or "graph reference"
            location = _safe_path(getattr(ref, "path", None))
            key = (identity.lower(), relationship, cycle_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ArchitectureGraphEvidenceRow(
                    identity=identity,
                    relationship_type=relationship,
                    reference_kind=reference_kind or graph_kind,
                    cycle_id=cycle_id,
                    location=location,
                    graph_artifact_ref=graph_ref_id,
                    finding_id=getattr(finding, "finding_id", None),
                    evidence_id=getattr(ref, "evidence_id", None),
                )
            )

    for edge in report.traceability_summary.sample_edges:
        identity = f"{edge.source_id} → {edge.target_id}"
        key = (identity.lower(), edge.relation, None)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            ArchitectureGraphEvidenceRow(
                identity=identity,
                relationship_type=edge.relation,
                reference_kind="traceability_edge",
                cycle_id=None,
                location=None,
                graph_artifact_ref=None,
                finding_id=None,
                evidence_id=None,
            )
        )

    rows.sort(
        key=lambda row: (
            (row.relationship_type or "").lower(),
            row.identity.lower(),
            row.evidence_id or "",
        )
    )
    return tuple(rows[:40])


def _measurements(
    findings: Sequence[Any],
) -> tuple[ArchitectureMeasurementRow, ...]:
    rows: list[ArchitectureMeasurementRow] = []
    seen: set[tuple[str, str, str | None]] = set()
    for finding in findings:
        finding_id = getattr(finding, "finding_id", None)
        for ref in getattr(finding, "evidence_refs", ()) or ():
            name = (getattr(ref, "measurement_name", None) or "").strip()
            measurement_value = getattr(ref, "measurement_value", None)
            if not name and measurement_value is None:
                continue
            observed = (
                str(measurement_value)
                if measurement_value is not None
                else "unavailable"
            )
            operator = (getattr(ref, "threshold_operator", None) or "").strip() or None
            threshold_value = getattr(ref, "threshold_value", None)
            threshold = (
                str(threshold_value) if threshold_value is not None else None
            )
            scope = getattr(ref, "measurement_scope", None)
            key = (name.lower() or "measurement", observed, finding_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ArchitectureMeasurementRow(
                    metric_name=name or "Measurement",
                    observed_value=observed,
                    threshold=threshold,
                    operator=operator,
                    scope=scope,
                    limitations=tuple(getattr(ref, "limitations", ()) or ()),
                    evidence_id=getattr(ref, "evidence_id", None),
                    finding_id=finding_id,
                )
            )
    rows.sort(key=lambda row: (row.metric_name.lower(), row.observed_value))
    return tuple(rows)


def _coverage_rows(report: ArchitectureReportSection) -> tuple[ArchitectureCoverageRow, ...]:
    rows = [
        ArchitectureCoverageRow(
            label=item.label,
            status=item.status,
            display=item.display,
            note=item.note,
        )
        for item in report.coverage_summary
        if str(item.status).strip().lower() not in {"unavailable", "unknown"}
        or str(item.display).strip().lower() not in {"unavailable", "unknown"}
    ]
    rows.sort(key=lambda row: row.label.lower())
    return tuple(rows)


def _limitations(
    report: ArchitectureReportSection,
    *,
    finding_links: Sequence[ArchitectureFindingLink],
    graph_rows: Sequence[ArchitectureGraphEvidenceRow],
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    for item in report.limitations:
        summary = (item.summary or "").strip()
        if not summary:
            continue
        if "business impact unknown" in summary.lower():
            continue
        if "phase " in summary.lower():
            continue
        notes.append(summary)
    if report.status in {"insufficient_evidence", "partially_succeeded"}:
        notes.append("Architecture coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("Architecture analysis did not produce a complete assessment.")
    if not finding_links:
        notes.append(
            "No architecture findings were produced within the assessed scope."
        )
    if not graph_rows and not (report.metadata.get("graph_fingerprint") or "").strip():
        notes.append("Graph evidence was unavailable for this assessment.")
    # Deduplicate, preserve order
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
    report: ArchitectureReportSection,
    finding_links: Sequence[ArchitectureFindingLink],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))
    for conclusion in report.conclusions:
        ranks.append(_CONFIDENCE_RANK.get(conclusion.confidence.lower(), 0))

    extraction = next(
        (area for area in report.coverage_summary if area.area_id == "extraction_coverage"),
        None,
    )
    classification = next(
        (
            area
            for area in report.coverage_summary
            if area.area_id == "classification_coverage"
        ),
        None,
    )
    if extraction is not None and extraction.ratio is not None and extraction.ratio < 0.75:
        ranks.append(1)
    if (
        classification is not None
        and classification.ratio is not None
        and classification.ratio < 0.75
    ):
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


def _safe_scope(values: Sequence[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        token = _safe_token(raw)
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return tuple(out)


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
    # Drop internal class-name style tokens that look like Python types.
    if text.startswith("<") and text.endswith(">"):
        return None
    return text


def _safe_path(path: str | None) -> str | None:
    return _safe_token(path)
