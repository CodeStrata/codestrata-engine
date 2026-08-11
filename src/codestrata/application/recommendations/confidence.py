"""Deterministic Recommendation Confidence derivation (Slice 5.5).

Weakest-support principle: Recommendation Confidence never exceeds the weakest
materially required supporting Finding Confidence. Priority and severity are
never inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.findings.finding_confidence import FindingConfidenceLevel
from codestrata.domain.recommendations.enums import RecommendationType
from codestrata.domain.recommendations.recommendation_confidence import (
    RecommendationConfidence,
    RecommendationConfidenceBasis,
    RecommendationConfidenceComponents,
    RecommendationConfidenceDerivationStatus,
    RecommendationConfidenceLevel,
    min_recommendation_confidence_level,
    recommendation_confidence_level_rank,
)
from codestrata.domain.traceability import EvidenceCompleteness


_FINDING_LEVELS = {
    "high": FindingConfidenceLevel.HIGH,
    "moderate": FindingConfidenceLevel.MODERATE,
    "limited": FindingConfidenceLevel.LIMITED,
    "unavailable": FindingConfidenceLevel.UNAVAILABLE,
}

_FINDING_TO_REC = {
    FindingConfidenceLevel.HIGH: RecommendationConfidenceLevel.HIGH,
    FindingConfidenceLevel.MODERATE: RecommendationConfidenceLevel.MODERATE,
    FindingConfidenceLevel.LIMITED: RecommendationConfidenceLevel.LIMITED,
    # Unavailable Finding Confidence caps Recommendation Confidence at Limited
    # (not Unavailable — that is reserved for legacy/missing support).
    FindingConfidenceLevel.UNAVAILABLE: RecommendationConfidenceLevel.LIMITED,
}


def derive_recommendation_confidence(
    *,
    supporting_finding_levels: Sequence[str] = (),
    primary_finding_level: str | None = None,
    supporting_finding_ids: Sequence[str] = (),
    primary_finding_id: str | None = None,
    evidence_completeness: str | EvidenceCompleteness | None = None,
    recommendation_type: str | RecommendationType | None = None,
    limitations: Sequence[str] = (),
    assessment_head_ids: Sequence[str] = (),
    unresolved_supporting_ids: Sequence[str] = (),
) -> RecommendationConfidence:
    """Derive Recommendation Confidence from supporting Finding Confidence."""

    rec_type = _normalize_type(recommendation_type)
    completeness = _normalize_completeness(evidence_completeness)
    limit_set = {str(item).strip() for item in limitations if str(item).strip()}
    supporting_ids = tuple(
        sorted({str(item).strip() for item in supporting_finding_ids if str(item).strip()})
    )
    unresolved = tuple(
        sorted({str(item).strip() for item in unresolved_supporting_ids if str(item).strip()})
    )
    heads = tuple(
        sorted({str(item).strip() for item in assessment_head_ids if str(item).strip()})
    )
    levels = _normalize_finding_levels(supporting_finding_levels)
    primary_level = _normalize_one_level(primary_finding_level)
    primary_id = str(primary_finding_id).strip() if primary_finding_id else None

    counts = _count_levels(levels)
    weakest = (
        min(levels, key=lambda item: recommendation_confidence_level_rank(_FINDING_TO_REC[item]))
        if levels
        else None
    )
    traceability_complete = (
        bool(supporting_ids)
        and not unresolved
        and completeness is EvidenceCompleteness.COMPLETE
        and primary_id is not None
        and primary_id in supporting_ids
        and len(levels) == len(supporting_ids)
    )
    components = RecommendationConfidenceComponents(
        supporting_finding_count=len(supporting_ids),
        high_finding_count=counts[FindingConfidenceLevel.HIGH],
        moderate_finding_count=counts[FindingConfidenceLevel.MODERATE],
        limited_finding_count=counts[FindingConfidenceLevel.LIMITED],
        unavailable_finding_count=counts[FindingConfidenceLevel.UNAVAILABLE],
        weakest_supporting_finding_confidence=(
            weakest.value if weakest is not None else None
        ),
        primary_finding_confidence=(
            primary_level.value if primary_level is not None else None
        ),
        evidence_completeness=completeness.value if completeness is not None else None,
        traceability_complete=traceability_complete,
        recommendation_type=rec_type.value if rec_type is not None else None,
        assessment_head_count=len(heads),
        limitations_count=len(limit_set),
    )

    # Legacy / missing support
    if rec_type is RecommendationType.LEGACY:
        legacy_basis = [RecommendationConfidenceBasis.LEGACY_RECOMMENDATION]
        if not supporting_ids:
            legacy_basis.append(
                RecommendationConfidenceBasis.MISSING_SUPPORTING_FINDINGS
            )
        return RecommendationConfidence.unavailable(
            basis=tuple(legacy_basis),
            limitations=tuple(
                sorted(
                    {
                        *limit_set,
                        "Legacy recommendation lacks canonical Finding Confidence support.",
                    }
                )
            ),
            component_summary=components,
        )

    if not supporting_ids or unresolved or len(levels) != len(supporting_ids):
        if rec_type is RecommendationType.FACT_BASED and not supporting_ids:
            return RecommendationConfidence(
                level=RecommendationConfidenceLevel.UNAVAILABLE,
                basis=(
                    RecommendationConfidenceBasis.FACT_BASED_RECOMMENDATION,
                    RecommendationConfidenceBasis.MISSING_SUPPORTING_FINDINGS,
                ),
                limitations=tuple(
                    sorted(
                        {
                            *limit_set,
                            "Fact-based recommendation lacks canonical Finding support.",
                        }
                    )
                ),
                derivation_status=RecommendationConfidenceDerivationStatus.UNAVAILABLE,
                component_summary=components,
            )
        return RecommendationConfidence.unavailable(
            basis=(RecommendationConfidenceBasis.MISSING_SUPPORTING_FINDINGS,),
            limitations=tuple(
                sorted(
                    {
                        *limit_set,
                        "Supporting findings are missing or unresolved; "
                        "Recommendation Confidence is Unavailable.",
                    }
                )
            ),
            component_summary=components,
        )

    if primary_id is not None and primary_id not in supporting_ids:
        return RecommendationConfidence.unavailable(
            basis=(RecommendationConfidenceBasis.MISSING_SUPPORTING_FINDINGS,),
            limitations=tuple(
                sorted(
                    {
                        *limit_set,
                        "primary_finding_id is not among supporting_finding_ids.",
                    }
                )
            ),
            component_summary=components,
        )

    # Fact-based without Finding Confidence contract
    if rec_type is RecommendationType.FACT_BASED:
        return RecommendationConfidence(
            level=RecommendationConfidenceLevel.LIMITED,
            basis=(
                RecommendationConfidenceBasis.FACT_BASED_RECOMMENDATION,
                RecommendationConfidenceBasis.LIMITED_SUPPORTING_FINDING,
            ),
            limitations=tuple(
                sorted(
                    {
                        *limit_set,
                        "Fact-based recommendation has no canonical Finding "
                        "Confidence contract; confidence remains Limited.",
                    }
                )
            ),
            derivation_status=RecommendationConfidenceDerivationStatus.PROVISIONAL,
            component_summary=components,
        )

    bases: list[RecommendationConfidenceBasis] = []
    out_limits = list(sorted(limit_set))
    caps: list[RecommendationConfidenceLevel] = [
        _FINDING_TO_REC[item] for item in levels
    ]

    if rec_type is RecommendationType.MERGED:
        bases.append(RecommendationConfidenceBasis.MERGED_RECOMMENDATION)
    if len(heads) > 1:
        bases.append(RecommendationConfidenceBasis.CROSS_HEAD_SUPPORT)
    if len(levels) == 1:
        bases.append(RecommendationConfidenceBasis.SINGLE_SUPPORTING_FINDING)
    elif len(set(levels)) == 1:
        bases.append(RecommendationConfidenceBasis.MULTIPLE_CONSISTENT_FINDINGS)

    if completeness is EvidenceCompleteness.COMPLETE and not unresolved:
        bases.append(RecommendationConfidenceBasis.COMPLETE_FINDING_TRACEABILITY)
    else:
        bases.append(RecommendationConfidenceBasis.PARTIAL_FINDING_TRACEABILITY)
        caps.append(RecommendationConfidenceLevel.LIMITED)

    unique = set(levels)
    if unique == {FindingConfidenceLevel.HIGH}:
        bases.append(RecommendationConfidenceBasis.ALL_SUPPORTING_FINDINGS_HIGH)
    elif FindingConfidenceLevel.LIMITED in unique:
        bases.append(RecommendationConfidenceBasis.LIMITED_SUPPORTING_FINDING)
    elif len(unique) > 1:
        bases.append(RecommendationConfidenceBasis.MIXED_FINDING_CONFIDENCE)

    if FindingConfidenceLevel.UNAVAILABLE in unique:
        bases.append(RecommendationConfidenceBasis.UNAVAILABLE_SUPPORTING_FINDING)
        out_limits.append(
            "One or more supporting findings have Unavailable Finding Confidence."
        )

    level = min_recommendation_confidence_level(tuple(caps))
    if (
        level is RecommendationConfidenceLevel.HIGH
        and RecommendationConfidenceBasis.PARTIAL_FINDING_TRACEABILITY in bases
    ):
        level = RecommendationConfidenceLevel.LIMITED
    if FindingConfidenceLevel.UNAVAILABLE in unique and level in {
        RecommendationConfidenceLevel.HIGH,
        RecommendationConfidenceLevel.MODERATE,
        RecommendationConfidenceLevel.UNAVAILABLE,
    }:
        level = RecommendationConfidenceLevel.LIMITED

    status = RecommendationConfidenceDerivationStatus.DERIVED
    if level in {
        RecommendationConfidenceLevel.LIMITED,
        RecommendationConfidenceLevel.UNAVAILABLE,
    } or completeness is not EvidenceCompleteness.COMPLETE:
        status = (
            RecommendationConfidenceDerivationStatus.UNAVAILABLE
            if level is RecommendationConfidenceLevel.UNAVAILABLE
            else RecommendationConfidenceDerivationStatus.PROVISIONAL
        )

    return RecommendationConfidence(
        level=level,
        basis=tuple(sorted(set(bases), key=lambda item: item.value)),
        limitations=tuple(sorted(set(out_limits))),
        derivation_status=status,
        component_summary=components,
    )


def apply_recommendation_confidence(
    recommendation: Any,
    *,
    findings: Sequence[Any] = (),
) -> Any:
    """Attach derived Recommendation Confidence onto a Recommendation-like object."""

    from codestrata.domain.recommendations.recommendation_confidence import (
        RecommendationConfidence,
    )

    findings_by_id = {
        str(getattr(item, "id", "") or getattr(item, "finding_id", "") or ""): item
        for item in findings
        if str(getattr(item, "id", "") or getattr(item, "finding_id", "") or "")
    }
    supporting = tuple(
        str(item)
        for item in (
            getattr(recommendation, "supporting_finding_ids", ())
            or getattr(recommendation, "related_finding_ids", ())
            or ()
        )
    )
    unresolved = tuple(item for item in supporting if item not in findings_by_id)
    levels: list[str] = []
    heads: list[str] = []
    for finding_id in supporting:
        finding = findings_by_id.get(finding_id)
        if finding is None:
            continue
        levels.append(_finding_level_of(finding))
        head = _assessment_head_of(finding)
        if head:
            heads.append(head)
    primary_id = getattr(recommendation, "primary_finding_id", None)
    primary_level = None
    if primary_id and primary_id in findings_by_id:
        primary_level = _finding_level_of(findings_by_id[primary_id])

    confidence = derive_recommendation_confidence(
        supporting_finding_levels=levels,
        primary_finding_level=primary_level,
        supporting_finding_ids=supporting,
        primary_finding_id=primary_id,
        evidence_completeness=getattr(recommendation, "evidence_completeness", None),
        recommendation_type=getattr(recommendation, "recommendation_type", None),
        limitations=tuple(getattr(recommendation, "limitations", ()) or ()),
        assessment_head_ids=heads,
        unresolved_supporting_ids=unresolved,
    )
    if isinstance(recommendation, Mapping):
        return recommendation
    return recommendation.model_copy(update={"recommendation_confidence": confidence})


def derive_customer_recommendation_confidence(
    *,
    supporting_finding_ids: Sequence[str],
    primary_finding_id: str | None,
    evidence_completeness: str | None,
    recommendation_type: str | None,
    limitations: Sequence[str],
    findings_by_id: Mapping[str, Any],
) -> RecommendationConfidence:
    """Derive confidence for a CustomerRecommendation using CustomerFinding map."""

    supporting = tuple(
        sorted({str(item).strip() for item in supporting_finding_ids if str(item).strip()})
    )
    unresolved = tuple(item for item in supporting if item not in findings_by_id)
    levels: list[str] = []
    heads: list[str] = []
    for finding_id in supporting:
        finding = findings_by_id.get(finding_id)
        if finding is None:
            continue
        levels.append(_finding_level_of(finding))
        head = _assessment_head_of(finding)
        if head:
            heads.append(head)
    primary_level = None
    if primary_finding_id and primary_finding_id in findings_by_id:
        primary_level = _finding_level_of(findings_by_id[primary_finding_id])
    return derive_recommendation_confidence(
        supporting_finding_levels=levels,
        primary_finding_level=primary_level,
        supporting_finding_ids=supporting,
        primary_finding_id=primary_finding_id,
        evidence_completeness=evidence_completeness,
        recommendation_type=recommendation_type,
        limitations=limitations,
        assessment_head_ids=heads,
        unresolved_supporting_ids=unresolved,
    )


def _finding_level_of(finding: Any) -> str:
    confidence = getattr(finding, "finding_confidence", None)
    if confidence is None and isinstance(finding, Mapping):
        confidence = finding.get("finding_confidence")
    if hasattr(confidence, "level"):
        return str(confidence.level.value if hasattr(confidence.level, "value") else confidence.level)
    if isinstance(confidence, Mapping) and confidence.get("level"):
        return str(confidence["level"]).strip().lower()
    direct = getattr(finding, "finding_confidence_level", None)
    if direct:
        return str(direct).strip().lower()
    return FindingConfidenceLevel.UNAVAILABLE.value


def _assessment_head_of(finding: Any) -> str | None:
    category = str(
        getattr(finding, "category", None)
        or (finding.get("category") if isinstance(finding, Mapping) else "")
        or ""
    ).strip().lower().replace(" ", "_").replace("-", "_")
    mapping = {
        "security": "security_intelligence",
        "dependency": "dependency_intelligence",
        "technical_debt": "technical_debt_intelligence",
        "maintainability": "technical_debt_intelligence",
        "architecture": "architecture_intelligence",
        "cloud": "cloud_readiness",
        "cloud_readiness": "cloud_readiness",
        "ai_readiness": "ai_readiness",
        "modernization": "modernization_assessment",
        "technology": "technology_inventory",
        "testing": "testing",
        "performance": "performance",
    }
    if category in mapping:
        return mapping[category]
    rule_id = str(
        getattr(finding, "rule_id", None)
        or (finding.get("rule_id") if isinstance(finding, Mapping) else "")
        or ""
    ).strip().lower()
    for prefix, head in (
        ("technical_debt.", "technical_debt_intelligence"),
        ("architecture.", "architecture_intelligence"),
        ("dependency.", "dependency_intelligence"),
        ("security.", "security_intelligence"),
        ("cloud.", "cloud_readiness"),
        ("ai_readiness.", "ai_readiness"),
        ("modernization.", "modernization_assessment"),
    ):
        if rule_id.startswith(prefix):
            return head
    return None


def _normalize_finding_levels(
    values: Sequence[str],
) -> tuple[FindingConfidenceLevel, ...]:
    out: list[FindingConfidenceLevel] = []
    for item in values:
        level = _normalize_one_level(item)
        out.append(level if level is not None else FindingConfidenceLevel.UNAVAILABLE)
    return tuple(out)


def _normalize_one_level(value: str | None) -> FindingConfidenceLevel | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    return _FINDING_LEVELS.get(key)


def _count_levels(
    levels: Sequence[FindingConfidenceLevel],
) -> dict[FindingConfidenceLevel, int]:
    counts = {level: 0 for level in FindingConfidenceLevel}
    for item in levels:
        counts[item] += 1
    return counts


def _normalize_completeness(
    value: str | EvidenceCompleteness | None,
) -> EvidenceCompleteness | None:
    if value is None:
        return None
    if isinstance(value, EvidenceCompleteness):
        return value
    text = str(value).strip().lower()
    try:
        return EvidenceCompleteness(text)
    except ValueError:
        return None


def _normalize_type(
    value: str | RecommendationType | None,
) -> RecommendationType | None:
    if value is None:
        return None
    if isinstance(value, RecommendationType):
        return value
    text = str(value).strip().lower()
    try:
        return RecommendationType(text)
    except ValueError:
        return None
