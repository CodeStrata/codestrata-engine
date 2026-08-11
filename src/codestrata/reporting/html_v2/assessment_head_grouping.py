"""Deterministic assessment-head grouping for customer HTML (Epic 3 Slice 3.1).

Uses structured category / rule-id prefix / pack presence only.
Never classifies from titles, descriptions, AI, or keyword heuristics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.reporting.html_v2.assessment_heads import (
    ASSESSMENT_RESULT_HEADS,
    AssessmentHead,
    assessment_head_anchor,
    assessment_head_title,
)
from codestrata.reporting.html_v2.models import FindingView, RecommendationView

# Explicit category → primary assessment head (structured FindingCategory / aliases).
_CATEGORY_TO_HEAD: dict[str, AssessmentHead] = {
    "security": AssessmentHead.SECURITY_INTELLIGENCE,
    "dependency": AssessmentHead.DEPENDENCY_INTELLIGENCE,
    "technical_debt": AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE,
    "maintainability": AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE,
    "architecture": AssessmentHead.ARCHITECTURE_INTELLIGENCE,
    "cloud": AssessmentHead.CLOUD_READINESS,
    "cloud_readiness": AssessmentHead.CLOUD_READINESS,
    "ai_readiness": AssessmentHead.AI_READINESS,
    "modernization": AssessmentHead.MODERNIZATION_ASSESSMENT,
    "technology": AssessmentHead.TECHNOLOGY_INVENTORY,
}

# Stable rule-id prefixes used by known packs (prefix match, longest first).
_RULE_PREFIX_TO_HEAD: tuple[tuple[str, AssessmentHead], ...] = (
    ("technical_debt.", AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE),
    ("ai_readiness.", AssessmentHead.AI_READINESS),
    ("ai-readiness.", AssessmentHead.AI_READINESS),
    ("architecture.", AssessmentHead.ARCHITECTURE_INTELLIGENCE),
    ("dependency.", AssessmentHead.DEPENDENCY_INTELLIGENCE),
    ("security.", AssessmentHead.SECURITY_INTELLIGENCE),
    ("cloud.", AssessmentHead.CLOUD_READINESS),
    ("modernization.", AssessmentHead.MODERNIZATION_ASSESSMENT),
)

AssessmentStatus = str  # assessed | partially_assessed | not_available | not_enabled | legacy_assessment
ConfidenceLabel = str  # high | moderate | limited | unavailable


def normalize_category(category: str | None) -> str:
    return (category or "").strip().lower().replace(" ", "_").replace("-", "_")


def classify_finding_head(
    finding: FindingView,
    *,
    rule_id: str | None = None,
) -> AssessmentHead | None:
    """Return primary assessment head for a finding, or None if unclassified."""

    category_head = _CATEGORY_TO_HEAD.get(normalize_category(finding.category))
    if category_head is not None:
        return category_head
    rid = (rule_id if rule_id is not None else finding.rule_id or "").strip().lower()
    for prefix, head in _RULE_PREFIX_TO_HEAD:
        if rid.startswith(prefix):
            return head
    return None


def classify_recommendation_head(
    recommendation: RecommendationView,
    *,
    finding_heads: Mapping[str, AssessmentHead | None],
) -> AssessmentHead | None:
    """Primary head for a recommendation.

    Order:
    1. Explicit recommendation category mapping
    2. Primary supporting finding head
    3. First supporting finding with a mapped head
    """

    category_head = _CATEGORY_TO_HEAD.get(normalize_category(recommendation.category))
    if category_head is not None:
        return category_head
    primary = recommendation.primary_finding_id
    if primary and primary in finding_heads and finding_heads[primary] is not None:
        return finding_heads[primary]
    for fid in recommendation.related_finding_ids:
        head = finding_heads.get(fid)
        if head is not None:
            return head
    return None


def confidence_from_completeness(values: Sequence[str]) -> ConfidenceLabel:
    """Legacy completeness-only label (compatibility).

    Assessment-Head Confidence derivation uses Finding Confidence via
    ``derive_assessment_head_confidence`` and must not rely on this helper.
    """

    normalized = [
        str(item or "").strip().lower()
        for item in values
        if str(item or "").strip()
    ]
    if not normalized:
        return "unavailable"
    if all(item == "complete" for item in normalized):
        return "high"
    if any(item in {"partial", "incomplete"} for item in normalized):
        return "limited"
    if any(item == "legacy" for item in normalized):
        return "unavailable"
    if any(item == "complete" for item in normalized):
        return "moderate"
    return "unavailable"


def confidence_label_text(label: ConfidenceLabel) -> str:
    return {
        "high": "High confidence",
        "moderate": "Moderate confidence",
        "limited": "Limited confidence",
        "unavailable": "Confidence unavailable",
    }.get(label, "Confidence unavailable")


def status_label_text(status: AssessmentStatus) -> str:
    return {
        "assessed": "Assessed",
        "partially_assessed": "Partially assessed",
        "not_available": "Not available",
        "not_enabled": "Not enabled",
        "legacy_assessment": "Legacy assessment",
    }.get(status, "Not available")


def aggregate_limitations(*groups: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
    return tuple(out)


def derive_head_status(
    *,
    pack_present: bool,
    pack_enabled: bool | None,
    finding_count: int,
    recommendation_count: int,
    has_inventory_facts: bool = False,
) -> AssessmentStatus:
    """Conservative status — zero findings never implies healthy/assessed alone."""

    if pack_enabled is False and not pack_present and finding_count == 0 and recommendation_count == 0:
        return "not_enabled"
    if pack_present:
        if finding_count or recommendation_count:
            return "assessed"
        # Pack ran but no entities — still assessed (execution proven), not "healthy".
        return "assessed"
    if has_inventory_facts:
        return "partially_assessed"
    if finding_count or recommendation_count:
        # Entities exist without a pack section — legacy / partial.
        return "legacy_assessment"
    return "not_available"


def build_assessment_head_sections(
    *,
    findings: Sequence[FindingView],
    recommendations: Sequence[RecommendationView],
    priority_actions: Sequence[RecommendationView],
    technologies_present: bool,
    architecture_present: bool,
    technical_debt_present: bool,
    dependency_present: bool,
    security_present: bool,
    cloud_present: bool,
    ai_readiness_present: bool,
    assessed_packs: Sequence[str] = (),
    not_assessed_packs: Sequence[tuple[str, str]] = (),
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[FindingView, ...],
    tuple[RecommendationView, ...],
]:
    """Build lightweight section dicts for each Assessment Results head."""

    finding_heads: dict[str, AssessmentHead | None] = {
        item.finding_id: classify_finding_head(item) for item in findings
    }
    findings_by_head: dict[AssessmentHead, list[FindingView]] = {h: [] for h in ASSESSMENT_RESULT_HEADS}
    unclassified_findings: list[FindingView] = []
    for item in findings:
        head = finding_heads.get(item.finding_id)
        if head is None or head not in findings_by_head:
            unclassified_findings.append(item)
        else:
            findings_by_head[head].append(item)

    rec_heads: dict[str, AssessmentHead | None] = {}
    recommendations_by_head: dict[AssessmentHead, list[RecommendationView]] = {
        h: [] for h in ASSESSMENT_RESULT_HEADS
    }
    unclassified_recommendations: list[RecommendationView] = []
    for item in recommendations:
        head = classify_recommendation_head(item, finding_heads=finding_heads)
        rec_heads[item.recommendation_id] = head
        if head is None or head not in recommendations_by_head:
            unclassified_recommendations.append(item)
        else:
            recommendations_by_head[head].append(item)

    # Related Priority Action IDs per head (links only — PA detail stays in Priority Actions).
    pa_ids_by_head: dict[AssessmentHead, list[str]] = {h: [] for h in ASSESSMENT_RESULT_HEADS}
    for action in priority_actions:
        head = rec_heads.get(action.recommendation_id)
        if head is None:
            head = classify_recommendation_head(action, finding_heads=finding_heads)
        if head is not None and head in pa_ids_by_head:
            pa_ids_by_head[head].append(action.recommendation_id)

    pack_enabled_lookup = _pack_enabled_map(assessed_packs, not_assessed_packs)
    pack_present = {
        AssessmentHead.TECHNOLOGY_INVENTORY: technologies_present,
        AssessmentHead.ARCHITECTURE_INTELLIGENCE: architecture_present,
        AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE: technical_debt_present,
        AssessmentHead.DEPENDENCY_INTELLIGENCE: dependency_present,
        AssessmentHead.SECURITY_INTELLIGENCE: security_present,
        AssessmentHead.CLOUD_READINESS: cloud_present,
        AssessmentHead.AI_READINESS: ai_readiness_present,
        AssessmentHead.MODERNIZATION_ASSESSMENT: False,  # synthesis; content routed separately
    }

    sections: list[dict[str, Any]] = []
    for head in ASSESSMENT_RESULT_HEADS:
        head_findings = tuple(findings_by_head[head])
        head_recs = tuple(recommendations_by_head[head])
        present = pack_present.get(head, False)
        enabled = pack_enabled_lookup.get(head)
        status = derive_head_status(
            pack_present=present,
            pack_enabled=enabled,
            finding_count=len(head_findings),
            recommendation_count=len(head_recs),
            has_inventory_facts=head is AssessmentHead.TECHNOLOGY_INVENTORY and technologies_present,
        )
        # Modernization is a synthesis section — partially assessed when opportunities/recs exist.
        if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
            if head_findings or head_recs:
                status = "partially_assessed"
            elif status == "not_available":
                status = "not_available"

        completeness_values = [f.evidence_completeness for f in head_findings] + [
            r.evidence_completeness for r in head_recs
        ]
        limitations = list(
            aggregate_limitations(
                *(f.limitations for f in head_findings),
                *(r.limitations for r in head_recs),
            )
        )
        limitations.extend(_default_limitations(head, status=status, pack_present=present))
        limitations = list(aggregate_limitations(limitations))

        from codestrata.application.assessment_heads.confidence import (
            confidence_label_from_head_confidence,
            derive_assessment_head_confidence,
        )
        from codestrata.domain.assessment_heads import assessment_head_confidence_to_json

        head_confidence = derive_assessment_head_confidence(
            head_id=head.value,
            assessment_status=status,
            finding_confidence_levels=tuple(
                f.finding_confidence_level or "unavailable" for f in head_findings
            ),
            evidence_completeness_values=completeness_values,
            limitations=limitations,
            activated=present or status in {"assessed", "partially_assessed", "legacy_assessment"},
            synthesized=head is AssessmentHead.MODERNIZATION_ASSESSMENT,
        )
        confidence, confidence_label = confidence_label_from_head_confidence(
            head_confidence
        )

        evidence_state = _evidence_state(
            status=status,
            finding_count=len(head_findings),
            has_refs=any(f.evidence_refs for f in head_findings),
        )
        placeholder = _placeholder_message(head, status=status)
        sections.append(
            {
                "head": head.value,
                "title": assessment_head_title(head),
                "anchor": assessment_head_anchor(head),
                "status": status,
                "status_label": status_label_text(status),
                "findings_count": len(head_findings),
                "recommendations_count": len(head_recs),
                "evidence_state": evidence_state,
                "confidence": confidence,
                "confidence_label": confidence_label,
                "assessment_head_confidence": assessment_head_confidence_to_json(
                    head_confidence
                ),
                "limitations": tuple(limitations),
                "findings": head_findings,
                "recommendations": head_recs,
                "related_priority_action_ids": tuple(pa_ids_by_head[head]),
                "placeholder_message": placeholder,
                "pack_content_available": present,
            }
        )

    return (
        tuple(sections),
        tuple(unclassified_findings),
        tuple(unclassified_recommendations),
    )


def _pack_enabled_map(
    assessed_packs: Sequence[str],
    not_assessed_packs: Sequence[tuple[str, str]],
) -> dict[AssessmentHead, bool | None]:
    assessed = {str(item).strip().lower() for item in assessed_packs}
    not_assessed = {str(item[0]).strip().lower() for item in not_assessed_packs}
    mapping = {
        "architecture": AssessmentHead.ARCHITECTURE_INTELLIGENCE,
        "technical_debt": AssessmentHead.TECHNICAL_DEBT_INTELLIGENCE,
        "dependency": AssessmentHead.DEPENDENCY_INTELLIGENCE,
        "security": AssessmentHead.SECURITY_INTELLIGENCE,
        "cloud": AssessmentHead.CLOUD_READINESS,
        "ai_readiness": AssessmentHead.AI_READINESS,
    }
    out: dict[AssessmentHead, bool | None] = {}
    for pack_id, head in mapping.items():
        if pack_id in assessed:
            out[head] = True
        elif pack_id in not_assessed:
            out[head] = False
        else:
            out[head] = None
    return out


def _evidence_state(*, status: AssessmentStatus, finding_count: int, has_refs: bool) -> str:
    if status in {"not_available", "not_enabled"}:
        return "unavailable"
    if finding_count == 0:
        return "none_reported"
    if has_refs:
        return "available"
    return "legacy_or_inline"


def _default_limitations(
    head: AssessmentHead,
    *,
    status: AssessmentStatus,
    pack_present: bool,
) -> tuple[str, ...]:
    notes: list[str] = []
    if status == "not_enabled":
        notes.append("This capability was not enabled for this assessment.")
    elif status == "not_available" and not pack_present:
        notes.append("Assessment not currently available for this section.")
    elif status == "legacy_assessment":
        notes.append(
            "Results were classified from structured category metadata without a "
            "dedicated pack assessment section."
        )
    if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
        notes.append(
            "Modernization Assessment is a synthesis of deterministic findings, "
            "recommendations, Priority Actions, and roadmap initiatives from "
            "enabled assessment heads."
        )
    return tuple(notes)


def _placeholder_message(head: AssessmentHead, *, status: AssessmentStatus) -> str | None:
    if status == "not_enabled":
        return "This capability was not enabled."
    if status == "not_available":
        return "Assessment not currently available."
    if status == "partially_assessed":
        if head is AssessmentHead.MODERNIZATION_ASSESSMENT:
            return None
        return "Detailed section implementation is scheduled for a later release."
    return None


UNCLASSIFIED_LIMITATION = (
    "Some assessment results could not yet be assigned to a customer-facing "
    "assessment section."
)
