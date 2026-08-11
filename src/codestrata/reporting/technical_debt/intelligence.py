"""Build Technical Debt Intelligence from existing report + findings (Epic 3 Slice 3.4).

Do NOT import from codestrata.reporting.html_v2 (circular import). Duck-type
findings/recommendations with Any + getattr.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.reporting.technical_debt.intelligence_models import (
    TechnicalDebtCoverageRow,
    TechnicalDebtFindingLink,
    TechnicalDebtHotspotRow,
    TechnicalDebtIntelligenceSection,
    TechnicalDebtMeasurementRow,
    TechnicalDebtOverviewFact,
    TechnicalDebtRecommendationLink,
)
from codestrata.reporting.technical_debt.models import TechnicalDebtReportSection

_BASE_LIMITATIONS = (
    "The assessed scope focused on static complexity signals.",
    "Broader technical debt categories were not evaluated.",
    "Duplication, deprecated technology, upgrade risk, and runtime "
    "maintainability were not assessed.",
    "Remediation cost, rewrite effort, and delivery impact were not estimated.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "low technical debt",
    "high technical debt",
    "rewrite required",
    "maintainability is poor",
    "developer productivity",
    "hard to change",
    "debt will delay",
    "no significant",
    "production-facing debt signals",
)

_EMPTY_FINDINGS_MESSAGE = (
    "No complexity-related technical debt findings were produced within the "
    "assessed scope. Zero findings do not mean low technical debt. Broader "
    "technical debt categories were not evaluated."
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

_SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
    "info": 4,
}

_GT_OPERATORS = {"gt", "gte", ">", ">="}


def build_technical_debt_intelligence(
    report: TechnicalDebtReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> TechnicalDebtIntelligenceSection | None:
    """Project Technical Debt Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    td_findings = tuple(item for item in findings if _is_technical_debt_finding(item))
    td_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in td_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    td_recs = tuple(
        item
        for item in recommendations
        if _is_technical_debt_recommendation(item, td_finding_ids)
    )

    finding_links = _finding_links(td_findings)
    recommendation_links = _recommendation_links(td_recs, report, td_finding_ids)
    measurements = _measurements(td_findings)
    hotspots = _hotspots(td_findings)
    coverage_rows = _coverage_rows(report)
    overview = _overview(
        report,
        finding_links=finding_links,
        recommendation_links=recommendation_links,
        measurements=measurements,
        hotspots=hotspots,
    )
    limitations = _limitations(report, finding_links=finding_links)
    confidence, confidence_label = _confidence(
        report=report,
        finding_links=finding_links,
        measurements=measurements,
        limitations=limitations,
    )
    empty_message = None if finding_links else _EMPTY_FINDINGS_MESSAGE

    return TechnicalDebtIntelligenceSection(
        status=report.status,
        status_label=report.status_label,
        status_summary=_safe_status_summary(report.status_summary),
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        measurements=measurements,
        hotspots=hotspots,
        findings=finding_links,
        recommendations=recommendation_links,
        coverage_rows=coverage_rows,
        limitations=limitations,
        finding_count=len(finding_links),
        recommendation_count=len(recommendation_links),
        measured_evidence_count=sum(
            1 for row in measurements if row.availability == "available"
        ),
        empty_findings_message=empty_message,
    )


def _is_technical_debt_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    return category in {"technical_debt", "maintainability"} or rule_id.startswith(
        "technical_debt."
    )


def _is_technical_debt_recommendation(
    item: Any,
    technical_debt_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category in {"technical_debt", "maintainability"}:
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(technical_debt_finding_ids)


def _safe_status_summary(text: str) -> str:
    lowered = text.lower()
    for fragment in _SOFT_CLAIM_FRAGMENTS:
        if fragment in lowered:
            return (
                "Technical debt assessment completed using static complexity "
                "evidence. Zero findings do not certify low technical debt."
            )
    return text


def _finding_links(
    findings: Sequence[Any],
) -> tuple[TechnicalDebtFindingLink, ...]:
    if not findings:
        return ()
    rows = [
        TechnicalDebtFindingLink(
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


def _finding_confidence_label(item: Any) -> str:
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
    report: TechnicalDebtReportSection,
    technical_debt_finding_ids: set[str],
) -> tuple[TechnicalDebtRecommendationLink, ...]:
    if recommendations:
        rows = [
            TechnicalDebtRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in technical_debt_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        TechnicalDebtRecommendationLink(
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


def _measurements(
    findings: Sequence[Any],
) -> tuple[TechnicalDebtMeasurementRow, ...]:
    rows: list[TechnicalDebtMeasurementRow] = []
    seen: set[tuple[str, str, str | None]] = set()
    for finding in findings:
        finding_id = getattr(finding, "finding_id", None)
        for ref in getattr(finding, "evidence_refs", ()) or ():
            name = (getattr(ref, "measurement_name", None) or "").strip()
            measurement_value = getattr(ref, "measurement_value", None)
            if not name and measurement_value is None:
                continue
            if measurement_value is None:
                observed = "unavailable"
                availability = "unavailable"
            else:
                observed = str(measurement_value)
                availability = "available"
            operator = (getattr(ref, "threshold_operator", None) or "").strip() or None
            threshold_value = getattr(ref, "threshold_value", None)
            threshold = (
                str(threshold_value) if threshold_value is not None else None
            )
            scope = getattr(ref, "measurement_scope", None)
            location = _safe_path(getattr(ref, "path", None))
            symbol = _safe_token(getattr(ref, "symbolic_reference", None))
            key = (name.lower() or "measurement", observed, finding_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                TechnicalDebtMeasurementRow(
                    metric_name=name or "Measurement",
                    observed_value=observed,
                    threshold=threshold,
                    operator=operator,
                    scope=scope,
                    location=location,
                    symbol=symbol,
                    availability=availability,
                    limitations=tuple(getattr(ref, "limitations", ()) or ()),
                    evidence_id=getattr(ref, "evidence_id", None),
                    finding_id=finding_id,
                )
            )
    rows.sort(
        key=lambda row: (
            row.metric_name.lower(),
            row.observed_value,
            row.finding_id or "",
        )
    )
    return tuple(rows)


def _hotspots(findings: Sequence[Any]) -> tuple[TechnicalDebtHotspotRow, ...]:
    """One hotspot per TD finding that has a measurement or a safe path.

    Never invent hotspots without a supporting finding_id.
    """

    rows: list[TechnicalDebtHotspotRow] = []
    for finding in findings:
        finding_id = str(getattr(finding, "finding_id", "") or "").strip()
        if not finding_id:
            continue

        measurement_ref = None
        for ref in getattr(finding, "evidence_refs", ()) or ():
            name = (getattr(ref, "measurement_name", None) or "").strip()
            value = getattr(ref, "measurement_value", None)
            if name or value is not None:
                measurement_ref = ref
                break

        path = None
        symbol = None
        metric_name = "—"
        observed_value = "unavailable"
        threshold = None
        operator = None
        exceedance = 0.0

        if measurement_ref is not None:
            path = _safe_path(getattr(measurement_ref, "path", None))
            symbol = _safe_token(getattr(measurement_ref, "symbolic_reference", None))
            metric_name = (
                (getattr(measurement_ref, "measurement_name", None) or "").strip()
                or "Measurement"
            )
            measurement_value = getattr(measurement_ref, "measurement_value", None)
            if measurement_value is None:
                observed_value = "unavailable"
            else:
                observed_value = str(measurement_value)
            threshold_value = getattr(measurement_ref, "threshold_value", None)
            threshold = (
                str(threshold_value) if threshold_value is not None else None
            )
            operator = (
                (getattr(measurement_ref, "threshold_operator", None) or "").strip()
                or None
            )
            exceedance = _exceedance_sort_key(
                observed_value=observed_value,
                threshold=threshold,
                operator=operator,
            )

        if path is None:
            for ref in getattr(finding, "evidence_refs", ()) or ():
                path = _safe_path(getattr(ref, "path", None))
                if path:
                    if symbol is None:
                        symbol = _safe_token(
                            getattr(ref, "symbolic_reference", None)
                        )
                    break

        if path is None:
            for node in getattr(finding, "affected_nodes", ()) or ():
                path = _safe_path(str(node))
                if path:
                    break

        if measurement_ref is None and path is None:
            continue

        rows.append(
            TechnicalDebtHotspotRow(
                finding_id=finding_id,
                path=path or "—",
                symbol=symbol or "—",
                metric_name=metric_name,
                observed_value=observed_value,
                threshold=threshold,
                operator=operator,
                severity=str(getattr(finding, "severity", "") or "unknown"),
                confidence=_finding_confidence_label(finding),
                evidence_ids=tuple(
                    getattr(ref, "evidence_id", "")
                    for ref in (getattr(finding, "evidence_refs", ()) or ())
                    if getattr(ref, "evidence_id", None)
                ),
                recommendation_ids=tuple(
                    getattr(finding, "driven_recommendation_ids", ()) or ()
                ),
                evidence_completeness=(
                    getattr(finding, "evidence_completeness", None) or None
                ),
                exceedance_sort_key=exceedance,
            )
        )

    rows.sort(
        key=lambda row: (
            _SEVERITY_RANK.get(row.severity.lower(), 99),
            -row.exceedance_sort_key,
            row.metric_name.lower(),
            row.path.lower(),
            row.symbol.lower(),
            row.finding_id,
        )
    )
    return tuple(rows)


def _exceedance_sort_key(
    *,
    observed_value: str,
    threshold: str | None,
    operator: str | None,
) -> float:
    if not threshold or not operator:
        return 0.0
    if operator.strip().lower() not in _GT_OPERATORS:
        return 0.0
    try:
        observed = float(observed_value)
        thresh = float(threshold)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, observed - thresh)


def _overview(
    report: TechnicalDebtReportSection,
    *,
    finding_links: Sequence[TechnicalDebtFindingLink],
    recommendation_links: Sequence[TechnicalDebtRecommendationLink],
    measurements: Sequence[TechnicalDebtMeasurementRow],
    hotspots: Sequence[TechnicalDebtHotspotRow],
) -> tuple[TechnicalDebtOverviewFact, ...]:
    measured_count = sum(1 for row in measurements if row.availability == "available")
    exceedance_count = sum(1 for row in hotspots if row.exceedance_sort_key > 0)
    paths = {row.path for row in hotspots if row.path and row.path != "—"}
    symbols = {row.symbol for row in hotspots if row.symbol and row.symbol != "—"}

    facts: list[TechnicalDebtOverviewFact] = [
        TechnicalDebtOverviewFact(label="Assessment status", value=report.status_label),
        TechnicalDebtOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Static complexity signals only",
        ),
        TechnicalDebtOverviewFact(
            label="Technical debt findings",
            value=str(len(finding_links)),
            note="Zero findings do not certify low technical debt",
        ),
        TechnicalDebtOverviewFact(
            label="Hotspots",
            value=str(len(hotspots)),
            note="Only findings with supporting evidence are listed",
        ),
        TechnicalDebtOverviewFact(
            label="Measured evidence",
            value=str(measured_count),
        ),
        TechnicalDebtOverviewFact(
            label="Threshold exceedances",
            value=str(exceedance_count),
        ),
        TechnicalDebtOverviewFact(
            label="Affected paths",
            value=str(len(paths)),
        ),
        TechnicalDebtOverviewFact(
            label="Affected symbols",
            value=str(len(symbols)),
        ),
        TechnicalDebtOverviewFact(
            label="Technical debt recommendations",
            value=str(len(recommendation_links)),
        ),
    ]
    for area in report.coverage_summary:
        if area.area_id in {"complexity_coverage", "debt_rule_coverage"}:
            facts.append(
                TechnicalDebtOverviewFact(
                    label=area.label,
                    value=area.display,
                    note=area.note,
                )
            )
    return tuple(facts)


def _coverage_rows(
    report: TechnicalDebtReportSection,
) -> tuple[TechnicalDebtCoverageRow, ...]:
    rows = [
        TechnicalDebtCoverageRow(
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
    report: TechnicalDebtReportSection,
    *,
    finding_links: Sequence[TechnicalDebtFindingLink],
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    for item in report.limitations:
        summary = (item.summary or "").strip()
        if not summary:
            continue
        lowered = summary.lower()
        if any(fragment in lowered for fragment in _SOFT_CLAIM_FRAGMENTS):
            continue
        if "business impact unknown" in lowered:
            continue
        if "phase " in lowered:
            continue
        notes.append(summary)
    if report.status in {"insufficient_evidence", "partially_succeeded"}:
        notes.append("Technical debt coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("Technical debt analysis did not produce a complete assessment.")
    if not finding_links:
        notes.append(
            "No complexity-related technical debt findings were produced within "
            "the assessed scope."
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
    report: TechnicalDebtReportSection,
    finding_links: Sequence[TechnicalDebtFindingLink],
    measurements: Sequence[TechnicalDebtMeasurementRow],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))

    if any(row.availability != "available" for row in measurements):
        ranks.append(1)

    for area in report.coverage_summary:
        if area.ratio is not None and area.ratio < 0.75:
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
    if text.startswith("<") and text.endswith(">"):
        return None
    return text


def _safe_path(path: str | None) -> str | None:
    return _safe_token(path)
