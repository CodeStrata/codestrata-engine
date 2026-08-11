"""Build Engineering Intelligence Summary (Epic 3 Slice 3.10).

Synthesis only: projects existing assessment-head sections, Priority Actions,
and roadmap counts. Does NOT import codestrata.reporting.html_v2 (circular
import). Duck-type entities with Any + getattr. Never invents findings,
recommendations, Priority Actions, scores, or maturity claims.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from codestrata.reporting.engineering_intelligence.intelligence_models import (
    EngineeringCountRow,
    EngineeringCoverageRow,
    EngineeringHeadSummary,
    EngineeringIntelligenceSection,
    EngineeringOverviewFact,
)

_BASE_LIMITATIONS = (
    "Based only on enabled assessment heads.",
    "Runtime behavior not evaluated.",
    "Disabled heads reduce completeness.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "healthy engineering organization",
    "healthy organization",
    "production ready",
    "modernization ready",
    "cloud ready",
    "ai ready",
    "agent ready",
    "enterprise ready",
    "transformation ready",
    "no issues found",
    "no security issues",
    "fully secure",
    "is secure",
    "are secure",
    "is maintainable",
    "are maintainable",
    "is scalable",
    "are scalable",
    "highly scalable",
    "well architected",
    "well-architected",
)

_SAFE_STATUS_SUMMARY = (
    "The assessment summarizes deterministic observations from the enabled "
    "assessment heads."
)

_CONFIDENCE_RANK = {
    "high": 3,
    "moderate": 2,
    "medium": 2,
    "limited": 1,
    "low": 1,
    "unavailable": 0,
    "unknown": 0,
    "legacy": 0,
}

_STATUS_RANK = {
    "assessed": 3,
    "partially_assessed": 2,
    "legacy_assessment": 1,
    "not_enabled": 0,
    "not_available": 0,
}

_COVERAGE_LABELS = {
    "unavailable": "Evidence unavailable",
    "none_reported": "No findings reported",
    "available": "Evidence available",
    "legacy_or_inline": "Legacy or inline evidence",
}

_ASSESSMENT_COVERAGE_LABELS = {
    "complete": "Complete coverage",
    "partial": "Partial coverage",
    "insufficient_evidence": "Insufficient evidence",
    "unavailable": "Coverage unavailable",
    "disabled": "Disabled",
    "not_applicable": "Not applicable",
}


def build_engineering_intelligence(
    *,
    assessment_heads: Sequence[Any] = (),
    priority_actions: Sequence[Any] = (),
    priority_actions_total: int | None = None,
    roadmap_report: Any | None = None,
    assessment_summary: Any | None = None,
    highest_finding_severity: str | None = None,
    unclassified_limitation: str | None = None,
    has_unclassified: bool = False,
) -> EngineeringIntelligenceSection:
    """Project Engineering Intelligence Summary from existing deterministic artifacts."""

    head_summaries = _head_summaries(assessment_heads)
    pa_total = (
        int(priority_actions_total)
        if priority_actions_total is not None
        else len(tuple(priority_actions))
    )
    priority_rows = _count_rows(
        (
            str(getattr(item, "priority", "") or "unknown").strip() or "unknown"
            for item in priority_actions
        )
    )
    horizon_rows = _count_rows(
        (
            str(getattr(item, "presentation_bucket", "") or "future").strip() or "future"
            for item in priority_actions
        )
    )

    total_findings = _summary_int(assessment_summary, "findings_count")
    if total_findings == 0:
        total_findings = sum(item.finding_count for item in head_summaries)
    total_recommendations = _summary_int(assessment_summary, "recommendations_count")
    if total_recommendations == 0:
        total_recommendations = sum(item.recommendation_count for item in head_summaries)

    phase_count, initiative_count = _roadmap_counts(roadmap_report)
    contributing = tuple(
        item
        for item in head_summaries
        if item.finding_count
        or item.recommendation_count
        or item.priority_action_count
        or item.status in {"assessed", "partially_assessed", "legacy_assessment"}
    )

    overview = _overview(
        head_summaries=head_summaries,
        total_findings=total_findings,
        total_recommendations=total_recommendations,
        pa_total=pa_total,
        highest_finding_severity=highest_finding_severity,
        assessment_summary=assessment_summary,
    )
    observations = _observations(
        head_summaries=head_summaries,
        total_findings=total_findings,
        total_recommendations=total_recommendations,
        pa_total=pa_total,
        highest_finding_severity=highest_finding_severity,
        phase_count=phase_count,
        assessment_summary=assessment_summary,
    )
    cross_head = _cross_head(
        total_findings=total_findings,
        total_recommendations=total_recommendations,
        pa_total=pa_total,
        phase_count=phase_count,
        initiative_count=initiative_count,
        contributing_count=len(contributing),
    )
    coverage_rows = _coverage_rows(
        head_summaries=head_summaries,
        pa_total=pa_total,
        phase_count=phase_count,
        initiative_count=initiative_count,
    )
    limitations = _limitations(
        assessment_heads=assessment_heads,
        unclassified_limitation=unclassified_limitation,
        has_unclassified=has_unclassified,
    )
    confidence, confidence_label = _confidence(head_summaries)
    status, status_label = _status(head_summaries)

    return EngineeringIntelligenceSection(
        status=status,
        status_label=status_label,
        status_summary=_SAFE_STATUS_SUMMARY,
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        head_summaries=head_summaries,
        observations=observations,
        cross_head_facts=cross_head,
        priority_action_total=pa_total,
        priority_by_priority=priority_rows,
        priority_by_horizon=horizon_rows,
        coverage_rows=coverage_rows,
        limitations=limitations,
        total_findings=total_findings,
        total_recommendations=total_recommendations,
        roadmap_phase_count=phase_count,
        roadmap_initiative_count=initiative_count,
        contributing_head_count=len(contributing),
    )


def scrub_soft_engineering_claims(text: str, *, fallback: str) -> str:
    """Replace soft engineering-readiness claims with a safe observational fallback."""

    if not text or not str(text).strip():
        return fallback
    if _contains_soft_claim(text):
        return fallback
    return str(text).strip()


def _contains_soft_claim(text: str) -> bool:
    lowered = str(text).lower()
    neutralized = (
        lowered.replace("does not establish", "")
        .replace("do not establish", "")
        .replace("not production ready", "")
        .replace("not cloud ready", "")
        .replace("not ai ready", "")
        .replace("not modernization ready", "")
        .replace("engineering intelligence summary", "")
        .replace("assessment heads", "")
    )
    return any(fragment in neutralized for fragment in _SOFT_CLAIM_FRAGMENTS)


def _head_summaries(assessment_heads: Sequence[Any]) -> tuple[EngineeringHeadSummary, ...]:
    rows: list[EngineeringHeadSummary] = []
    for item in assessment_heads:
        head_id = str(getattr(item, "head", "") or "").strip()
        title = str(getattr(item, "title", "") or "").strip()
        anchor = str(getattr(item, "anchor", "") or "").strip()
        if not head_id or not title or not anchor:
            continue
        evidence_state = str(getattr(item, "evidence_state", "") or "unavailable").strip()
        coverage_payload = getattr(item, "assessment_coverage", None)
        coverage_status = None
        if isinstance(coverage_payload, dict):
            coverage_status = str(coverage_payload.get("status") or "").strip().lower()
        elif coverage_payload is not None:
            coverage_status = str(getattr(coverage_payload, "status", "") or "").strip().lower()
        if coverage_status:
            coverage = _ASSESSMENT_COVERAGE_LABELS.get(
                coverage_status,
                coverage_status.replace("_", " ").title(),
            )
        else:
            coverage = _COVERAGE_LABELS.get(evidence_state, evidence_state or "unavailable")
        pa_ids = tuple(getattr(item, "related_priority_action_ids", ()) or ())
        rows.append(
            EngineeringHeadSummary(
                head_id=head_id,
                title=title,
                anchor=anchor,
                status=str(getattr(item, "status", "") or "not_available").strip()
                or "not_available",
                status_label=str(getattr(item, "status_label", "") or "Not available").strip()
                or "Not available",
                finding_count=int(getattr(item, "findings_count", 0) or 0),
                recommendation_count=int(getattr(item, "recommendations_count", 0) or 0),
                confidence=str(getattr(item, "confidence", "") or "unavailable").strip()
                or "unavailable",
                confidence_label=str(
                    getattr(item, "confidence_label", "") or "Confidence unavailable"
                ).strip()
                or "Confidence unavailable",
                coverage=coverage,
                priority_action_count=len(pa_ids),
            )
        )
    return tuple(rows)


def _summary_int(summary: Any | None, field: str) -> int:
    if summary is None:
        return 0
    try:
        return max(0, int(getattr(summary, field, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _roadmap_counts(roadmap_report: Any | None) -> tuple[int, int]:
    if roadmap_report is None:
        return 0, 0
    phases = tuple(getattr(roadmap_report, "phases", ()) or ())
    initiatives = int(getattr(roadmap_report, "initiatives_total", 0) or 0)
    if initiatives == 0:
        initiatives = len(tuple(getattr(roadmap_report, "initiatives", ()) or ()))
    # Count phases that actually carry initiatives.
    phase_with_items = 0
    for phase in phases:
        inits = tuple(getattr(phase, "initiatives", ()) or ())
        ids = tuple(getattr(phase, "initiative_ids", ()) or ())
        if inits or ids:
            phase_with_items += 1
    if phase_with_items == 0 and phases:
        phase_with_items = len(phases) if initiatives else 0
    return phase_with_items, initiatives


def _count_rows(values) -> tuple[EngineeringCountRow, ...]:
    counter: Counter[str] = Counter()
    for value in values:
        key = str(value or "").strip() or "unknown"
        counter[key] += 1
    return tuple(
        EngineeringCountRow(label=label, count=count)
        for label, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    )


def _overview(
    *,
    head_summaries: Sequence[EngineeringHeadSummary],
    total_findings: int,
    total_recommendations: int,
    pa_total: int,
    highest_finding_severity: str | None,
    assessment_summary: Any | None,
) -> tuple[EngineeringOverviewFact, ...]:
    assessed = sum(
        1
        for item in head_summaries
        if item.status in {"assessed", "partially_assessed", "legacy_assessment"}
    )
    coverage_complete = sum(
        1 for item in head_summaries if item.coverage == "Complete coverage"
    )
    coverage_partial = sum(
        1 for item in head_summaries if item.coverage == "Partial coverage"
    )
    coverage_unavailable = sum(
        1
        for item in head_summaries
        if item.coverage
        in {"Coverage unavailable", "Insufficient evidence", "Not applicable"}
    )
    coverage_disabled = sum(
        1 for item in head_summaries if item.coverage == "Disabled"
    )
    facts: list[EngineeringOverviewFact] = [
        EngineeringOverviewFact(
            label="Assessment heads with results",
            value=f"{assessed} / {len(head_summaries)}",
            note="Counts reflect enabled assessment heads only",
        ),
        EngineeringOverviewFact(
            label="Head coverage complete / partial / unavailable",
            value=f"{coverage_complete} / {coverage_partial} / {coverage_unavailable}",
            note="Canonical Assessment Coverage statuses; not an averaged percentage",
        ),
        EngineeringOverviewFact(
            label="Disabled assessment heads",
            value=str(coverage_disabled),
            note="Disabled heads are excluded from assessed-scope coverage aggregates",
        ),
        EngineeringOverviewFact(
            label="Findings",
            value=str(total_findings),
        ),
        EngineeringOverviewFact(
            label="Recommendations",
            value=str(total_recommendations),
        ),
        EngineeringOverviewFact(
            label="Priority Actions",
            value=str(pa_total),
            note="Canonical Priority Actions; see Priority Actions section",
        ),
    ]
    rules = _summary_int(assessment_summary, "rules_evaluated")
    if rules:
        facts.insert(
            0,
            EngineeringOverviewFact(
                label="Checks assessed",
                value=str(rules),
            ),
        )
    if highest_finding_severity:
        facts.append(
            EngineeringOverviewFact(
                label="Highest finding severity",
                value=str(highest_finding_severity),
            )
        )
    return tuple(facts)


def _observations(
    *,
    head_summaries: Sequence[EngineeringHeadSummary],
    total_findings: int,
    total_recommendations: int,
    pa_total: int,
    highest_finding_severity: str | None,
    phase_count: int,
    assessment_summary: Any | None,
) -> tuple[str, ...]:
    """Deterministic factual observations only — no maturity narrative."""

    notes: list[str] = []
    enabled = sum(
        1
        for item in head_summaries
        if item.status not in {"not_available", "not_enabled"}
    )
    notes.append(
        f"{enabled} assessment head(s) contributed deterministic results within "
        "the assessed scope."
    )
    notes.append(
        f"{total_findings} finding(s) and {total_recommendations} recommendation(s) "
        "were produced across enabled assessment heads."
    )
    notes.append(
        f"{pa_total} Priority Action(s) were produced from grounded recommendations."
    )
    if highest_finding_severity:
        notes.append(
            f"Highest finding severity observed: {highest_finding_severity}."
        )
    if phase_count:
        notes.append(
            f"{phase_count} roadmap phase(s) are represented in the Priority "
            "Action-backed plan."
        )
    by_sev = tuple(getattr(assessment_summary, "findings_by_severity", ()) or ())
    if by_sev:
        parts = [
            f"{name}: {count}"
            for name, count in by_sev
            if str(name).strip() and int(count or 0) > 0
        ]
        if parts:
            notes.append("Findings by severity — " + "; ".join(parts) + ".")
    # Soft-scrub any accidental soft claims in generated text.
    return tuple(
        scrub_soft_engineering_claims(note, fallback=_SAFE_STATUS_SUMMARY)
        for note in notes
        if note.strip()
    )


def _cross_head(
    *,
    total_findings: int,
    total_recommendations: int,
    pa_total: int,
    phase_count: int,
    initiative_count: int,
    contributing_count: int,
) -> tuple[EngineeringOverviewFact, ...]:
    return (
        EngineeringOverviewFact(label="Total findings", value=str(total_findings)),
        EngineeringOverviewFact(
            label="Total recommendations", value=str(total_recommendations)
        ),
        EngineeringOverviewFact(
            label="Total Priority Actions", value=str(pa_total)
        ),
        EngineeringOverviewFact(
            label="Roadmap phases", value=str(phase_count)
        ),
        EngineeringOverviewFact(
            label="Roadmap initiatives", value=str(initiative_count)
        ),
        EngineeringOverviewFact(
            label="Contributing assessment heads",
            value=str(contributing_count),
        ),
    )


def _coverage_rows(
    *,
    head_summaries: Sequence[EngineeringHeadSummary],
    pa_total: int,
    phase_count: int,
    initiative_count: int,
) -> tuple[EngineeringCoverageRow, ...]:
    rows: list[EngineeringCoverageRow] = []
    for item in head_summaries:
        rows.append(
            EngineeringCoverageRow(
                label=item.title,
                status=item.status,
                display=item.coverage,
                note=item.confidence_label,
            )
        )
    rows.append(
        EngineeringCoverageRow(
            label="Priority Actions",
            status="available" if pa_total else "none_reported",
            display=str(pa_total),
            note="Canonical Priority Action universe",
        )
    )
    rows.append(
        EngineeringCoverageRow(
            label="Roadmap",
            status="available" if phase_count or initiative_count else "none_reported",
            display=f"{phase_count} phase(s), {initiative_count} initiative(s)",
            note="Planning guidance only; see Roadmap section",
        )
    )
    return tuple(rows)


def _limitations(
    *,
    assessment_heads: Sequence[Any],
    unclassified_limitation: str | None,
    has_unclassified: bool,
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    disabled = [
        item
        for item in assessment_heads
        if str(getattr(item, "status", "") or "").strip()
        in {"not_enabled", "not_available"}
    ]
    if disabled:
        notes.append(
            "Some assessment heads were not enabled or not available, which "
            "reduces completeness."
        )
    notes.extend(aggregate_head_limitations(assessment_heads))
    if has_unclassified and unclassified_limitation:
        text = str(unclassified_limitation).strip()
        if text and not _contains_soft_claim(text):
            notes.append(text)

    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.strip()
        if not key or key.lower() in seen:
            continue
        if _contains_soft_claim(key):
            continue
        seen.add(key.lower())
        out.append(key)
    return tuple(out)


def aggregate_head_limitations(assessment_heads: Sequence[Any]) -> tuple[str, ...]:
    """Collect and dedupe limitations from assessment-head sections."""

    notes: list[str] = []
    for item in assessment_heads:
        for note in getattr(item, "limitations", ()) or ():
            text = str(note or "").strip()
            if not text or _contains_soft_claim(text):
                continue
            if "scheduled for a later release" in text.lower():
                continue
            notes.append(text)
    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(note)
    return tuple(out)


def _confidence(
    head_summaries: Sequence[EngineeringHeadSummary],
) -> tuple[str, str]:
    ranks: list[int] = []
    for item in head_summaries:
        if item.status in {"not_enabled", "not_available"}:
            continue
        ranks.append(_CONFIDENCE_RANK.get(item.confidence.lower(), 0))
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


def _status(
    head_summaries: Sequence[EngineeringHeadSummary],
) -> tuple[str, str]:
    if not head_summaries:
        return "not_available", "Not available"
    active = [
        item
        for item in head_summaries
        if item.status not in {"not_enabled", "not_available"}
    ]
    if not active:
        return "not_available", "Not available"
    ranks = [_STATUS_RANK.get(item.status, 0) for item in active]
    weakest = min(ranks) if ranks else 0
    if weakest >= 3 and all(item.status == "assessed" for item in active):
        return "assessed", "Assessed"
    if weakest >= 1:
        return "partially_assessed", "Partially assessed"
    return "not_available", "Not available"
