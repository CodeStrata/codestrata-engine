"""Deterministic Recommendation priority calibration (Epic 5 Slice 5.14).

Flow:
  Recommendation Confidence → Recommendation Priority Assessment →
  projection onto Recommendation.priority

Priority is ordering utility only. Precision/Recall/FP/FN, title text, duplicate
counts, and raw correlation counts never enter the score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.application.recommendations.priority_policies import (
    SEVERITY_POINTS,
    RecommendationPriorityPolicy,
    resolve_priority_policy,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.findings.finding_confidence import FindingConfidenceLevel
from codestrata.domain.recommendations.enums import RecommendationPriority, RecommendationType
from codestrata.domain.recommendations.priority import (
    BAND_HIGH_MIN,
    BAND_IMMEDIATE_MIN,
    BAND_MEDIUM_MIN,
    PRIORITY_SCORE_MAX,
    RecommendationPriorityAssessment,
    RecommendationPriorityBasis,
    RecommendationPriorityComponents,
    PriorityCalibrationStatus,
    clamp_score,
    priority_for_score,
    score_for_priority,
)
from codestrata.domain.recommendations.recommendation_confidence import (
    RecommendationConfidenceLevel,
)
from codestrata.domain.traceability import EvidenceCompleteness
from codestrata.domain.traceability.validators import normalize_limitations

_SEVERITY_RANK = {
    FindingSeverity.INFORMATIONAL: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}

_PRIORITY_RANK = {
    RecommendationPriority.LOW: 0,
    RecommendationPriority.MEDIUM: 1,
    RecommendationPriority.HIGH: 2,
    RecommendationPriority.IMMEDIATE: 3,
}

_REC_CONF_RANK = {
    RecommendationConfidenceLevel.UNAVAILABLE: 0,
    RecommendationConfidenceLevel.LIMITED: 1,
    RecommendationConfidenceLevel.MODERATE: 2,
    RecommendationConfidenceLevel.HIGH: 3,
}

# Presentation buckets from calibrated 0–100 score (not the legacy composite).
BUCKET_IMMEDIATE_MIN = BAND_IMMEDIATE_MIN
BUCKET_NEAR_TERM_MIN = BAND_HIGH_MIN


def calibrate_recommendation_priority(
    recommendation: Any,
    *,
    findings: Sequence[Any] = (),
    policy: RecommendationPriorityPolicy | None = None,
) -> RecommendationPriorityAssessment:
    """Compute canonical priority assessment for one Recommendation."""

    provider_id = str(getattr(recommendation, "provider_id", "") or "").strip()
    findings_by_id = {str(getattr(item, "id", "")): item for item in findings}

    supporting_ids = tuple(
        str(item)
        for item in (
            getattr(recommendation, "supporting_finding_ids", None)
            or getattr(recommendation, "related_finding_ids", ())
            or ()
        )
        if str(item).strip()
    )
    supporting = [findings_by_id[item] for item in supporting_ids if item in findings_by_id]

    rec_type = getattr(recommendation, "recommendation_type", None)
    rec_type_value = (
        rec_type.value if isinstance(rec_type, RecommendationType) else str(rec_type or "")
    )
    if isinstance(rec_type, RecommendationType):
        is_legacy = rec_type is RecommendationType.LEGACY and not supporting_ids
    else:
        is_legacy = str(rec_type or "").lower() == "legacy" and not supporting_ids

    resolved = policy or resolve_priority_policy(
        provider_id or None,
        recommendation_type=rec_type_value,
        has_supporting_findings=bool(supporting_ids),
    )

    if is_legacy and resolved.policy_id == "priority.legacy.compatibility":
        return RecommendationPriorityAssessment.legacy(
            priority=getattr(recommendation, "priority", RecommendationPriority.LOW)
            or RecommendationPriority.LOW,
            limitations=tuple(resolved.limitations),
        )

    highest_severity = _highest_severity(supporting)
    severity_points = 0
    if resolved.severity_weight_enabled and highest_severity is not None:
        severity_points = min(
            resolved.max_severity_points,
            SEVERITY_POINTS.get(highest_severity, 0),
        )

    base = resolved.base_score
    score = base + severity_points
    basis: list[RecommendationPriorityBasis] = [
        RecommendationPriorityBasis.PROVIDER_DEFAULT,
        RecommendationPriorityBasis.EXPLICIT_POLICY,
    ]
    if severity_points:
        basis.append(RecommendationPriorityBasis.CALIBRATED_FINDING_SEVERITY)
    if resolved.allows_direct_security_exposure:
        basis.append(RecommendationPriorityBasis.DIRECT_SECURITY_EXPOSURE)
    # Direct-exposure policies may reach Immediate for Critical/High calibrated
    # severity (credential/private-key style remediation). Severity alone still
    # does not force Immediate when the policy forbids it.
    if (
        resolved.allows_immediate
        and resolved.allows_direct_security_exposure
        and highest_severity
        in {FindingSeverity.CRITICAL, FindingSeverity.HIGH}
        and score < BAND_IMMEDIATE_MIN
    ):
        score = BAND_IMMEDIATE_MIN
        basis.append(RecommendationPriorityBasis.CALIBRATED_FINDING_SEVERITY)
        basis.append(RecommendationPriorityBasis.DIRECT_SECURITY_EXPOSURE)

    # Deterministic scope: distinct supporting Findings only (not duplicate count).
    affected = _affected_subject_count(recommendation, supporting)
    scope_adj = 0
    if resolved.scope_adjustment_max and affected is not None and affected >= 2:
        scope_adj = min(resolved.scope_adjustment_max, min(3, affected - 1))
        if scope_adj:
            score += scope_adj
            basis.append(RecommendationPriorityBasis.DETERMINISTIC_SCOPE)
            basis.append(RecommendationPriorityBasis.AFFECTED_SUBJECT_COUNT)

    correlation_adj = 0
    correlation_count = _correlation_signal_count(recommendation, supporting)
    if (
        resolved.correlation_aware
        and resolved.correlation_adjustment_max
        and _is_correlation_aware_recommendation(recommendation)
        and len(supporting) >= 2
    ):
        correlation_adj = min(resolved.correlation_adjustment_max, 5)
        score += correlation_adj
        basis.append(RecommendationPriorityBasis.CORRELATED_SUPPORTING_FINDINGS)

    limitations = list(resolved.limitations)
    limitations.extend(getattr(recommendation, "limitations", ()) or ())

    # Evidence completeness cap (partial/legacy).
    completeness = getattr(recommendation, "evidence_completeness", None)
    completeness_value = (
        completeness.value if hasattr(completeness, "value") else str(completeness or "")
    ).lower()
    if completeness_value in {
        EvidenceCompleteness.PARTIAL.value,
        EvidenceCompleteness.LEGACY.value,
        EvidenceCompleteness.UNAVAILABLE.value,
    }:
        score = min(score, BAND_HIGH_MIN + 5)
        basis.append(RecommendationPriorityBasis.EVIDENCE_COMPLETENESS)
        limitations.append("Evidence completeness constrains priority.")

    # Recommendation Confidence is the primary confidence input (no Finding double-count).
    conf_level = _recommendation_confidence_level(recommendation)
    score, conf_basis, conf_limits = _apply_confidence_caps(
        score,
        level=conf_level,
        policy=resolved,
    )
    basis.extend(conf_basis)
    limitations.extend(conf_limits)

    # Context caps from supporting Findings (test/docs/example).
    if _non_production_context(supporting):
        if not resolved.allows_direct_security_exposure:
            score = min(score, BAND_MEDIUM_MIN + 15)
            basis.append(RecommendationPriorityBasis.CONTEXT_CAP)
            limitations.append("Non-production context caps unsupported urgency.")
        else:
            basis.append(RecommendationPriorityBasis.PRODUCTION_CONTEXT)

    if any(
        "static" in str(item).lower()
        for item in (getattr(recommendation, "limitations", ()) or ())
    ):
        basis.append(RecommendationPriorityBasis.STATIC_ONLY_LIMITATION)

    calibration_status = resolved.calibration_status
    if conf_level is RecommendationConfidenceLevel.UNAVAILABLE:
        calibration_status = PriorityCalibrationStatus.LEGACY
        basis.append(RecommendationPriorityBasis.LEGACY_RECOMMENDATION)
    elif conf_level is RecommendationConfidenceLevel.LIMITED:
        if calibration_status is PriorityCalibrationStatus.CALIBRATED:
            calibration_status = PriorityCalibrationStatus.PROVISIONAL

    # Clamp to policy-allowed priorities.
    score = clamp_score(score)
    priority = priority_for_score(score)
    if priority not in resolved.allowed_priorities:
        allowed_sorted = sorted(
            resolved.allowed_priorities,
            key=lambda item: _PRIORITY_RANK[item],
            reverse=True,
        )
        # Pick highest allowed at or below target.
        chosen = allowed_sorted[-1]
        for candidate in allowed_sorted:
            if _PRIORITY_RANK[candidate] <= _PRIORITY_RANK[priority]:
                chosen = candidate
                break
        priority = chosen
        score = _score_within_band(priority, score)

    if priority is RecommendationPriority.IMMEDIATE and not resolved.allows_immediate:
        priority = RecommendationPriority.HIGH
        score = min(score, BAND_IMMEDIATE_MIN - 1)

    score = clamp_score(score)
    priority = priority_for_score(score)
    if priority not in resolved.allowed_priorities:
        priority = max(
            resolved.allowed_priorities,
            key=lambda item: _PRIORITY_RANK[item],
        )
        score = score_for_priority(priority)

    heads = {
        str(getattr(item, "category", "") or "").strip().lower()
        for item in supporting
        if str(getattr(item, "category", "") or "").strip()
    }
    weakest_fc = _weakest_finding_confidence(supporting)
    effort = None
    metadata = getattr(recommendation, "metadata", None) or {}
    if isinstance(metadata, Mapping) and metadata.get("effort"):
        effort = str(metadata.get("effort"))

    components = RecommendationPriorityComponents(
        supporting_finding_count=len(supporting_ids),
        highest_finding_severity=highest_severity.value if highest_severity else None,
        weakest_finding_confidence=weakest_fc,
        recommendation_confidence=conf_level.value if conf_level else None,
        evidence_completeness=completeness_value or None,
        affected_subject_count=affected,
        assessment_head_count=len(heads),
        correlation_count=correlation_count,
        effort=effort,
        base_score=base,
        calibrated_score=score,
        priority=priority,
        limitations_count=len(normalize_limitations(limitations)),
    )

    # Deduplicate basis while preserving order.
    seen: set[str] = set()
    unique_basis: list[RecommendationPriorityBasis] = []
    for item in basis:
        if item.value in seen:
            continue
        seen.add(item.value)
        unique_basis.append(item)

    return RecommendationPriorityAssessment(
        priority=priority,
        score=score,
        basis=tuple(unique_basis),
        calibration_status=calibration_status,
        limitations=normalize_limitations(limitations),
        component_summary=components,
        policy_id=resolved.policy_id,
    )


def apply_recommendation_priority(
    recommendation: Any,
    *,
    findings: Sequence[Any] = (),
    policy: RecommendationPriorityPolicy | None = None,
) -> Any:
    """Attach priority_assessment and project priority onto the Recommendation."""

    assessment = calibrate_recommendation_priority(
        recommendation,
        findings=findings,
        policy=policy,
    )
    if isinstance(recommendation, Mapping):
        return recommendation
    updates: dict[str, Any] = {
        "priority": assessment.priority,
        "priority_assessment": assessment,
    }
    # Union assessment limitations without dropping existing ones.
    existing = tuple(getattr(recommendation, "limitations", ()) or ())
    merged_limits = normalize_limitations((*existing, *assessment.limitations))
    if merged_limits != existing:
        updates["limitations"] = merged_limits
    return recommendation.model_copy(update=updates)


def presentation_bucket_for_calibrated_score(score: float | int) -> str:
    """Map 0–100 calibrated score onto Immediate / Near Term / Future."""

    value = float(score)
    if value >= BUCKET_IMMEDIATE_MIN:
        return "immediate"
    if value >= BUCKET_NEAR_TERM_MIN:
        return "near_term"
    return "future"


def priority_assessment_to_json(
    assessment: RecommendationPriorityAssessment,
) -> dict[str, Any]:
    payload = assessment.canonical_dict()
    # Customer-facing: present IMMEDIATE as critical where helpful.
    if payload.get("priority") == RecommendationPriority.IMMEDIATE.value:
        # Keep enum value for compatibility; component_summary already has priority.
        pass
    return dict(sorted(payload.items(), key=lambda pair: str(pair[0])))


def _highest_severity(findings: Sequence[Any]) -> FindingSeverity | None:
    best: FindingSeverity | None = None
    best_rank = -1
    for item in findings:
        severity = getattr(item, "severity", None)
        if severity is None:
            continue
        if not isinstance(severity, FindingSeverity):
            try:
                severity = FindingSeverity(str(severity).strip().lower())
            except ValueError:
                continue
        rank = _SEVERITY_RANK.get(severity, -1)
        if rank > best_rank:
            best = severity
            best_rank = rank
    return best


def _weakest_finding_confidence(findings: Sequence[Any]) -> str | None:
    if not findings:
        return None
    from codestrata.domain.findings.finding_confidence import (
        finding_confidence_level_rank,
    )

    weakest = FindingConfidenceLevel.HIGH
    for item in findings:
        level = _finding_confidence_level(item)
        if finding_confidence_level_rank(level) < finding_confidence_level_rank(weakest):
            weakest = level
    return weakest.value


def _finding_confidence_level(finding: Any) -> FindingConfidenceLevel:
    confidence = getattr(finding, "finding_confidence", None)
    if confidence is None and isinstance(finding, Mapping):
        confidence = finding.get("finding_confidence")
    if hasattr(confidence, "level"):
        level = confidence.level
        if isinstance(level, FindingConfidenceLevel):
            return level
        try:
            return FindingConfidenceLevel(str(level).strip().lower())
        except ValueError:
            return FindingConfidenceLevel.UNAVAILABLE
    if isinstance(confidence, Mapping) and confidence.get("level"):
        try:
            return FindingConfidenceLevel(str(confidence["level"]).strip().lower())
        except ValueError:
            return FindingConfidenceLevel.UNAVAILABLE
    return FindingConfidenceLevel.UNAVAILABLE


def _recommendation_confidence_level(
    recommendation: Any,
) -> RecommendationConfidenceLevel:
    confidence = getattr(recommendation, "recommendation_confidence", None)
    if confidence is None and isinstance(recommendation, Mapping):
        confidence = recommendation.get("recommendation_confidence")
    if hasattr(confidence, "level"):
        level = confidence.level
        if isinstance(level, RecommendationConfidenceLevel):
            return level
        try:
            return RecommendationConfidenceLevel(str(level).strip().lower())
        except ValueError:
            return RecommendationConfidenceLevel.UNAVAILABLE
    if isinstance(confidence, Mapping) and confidence.get("level"):
        try:
            return RecommendationConfidenceLevel(str(confidence["level"]).strip().lower())
        except ValueError:
            return RecommendationConfidenceLevel.UNAVAILABLE
    return RecommendationConfidenceLevel.UNAVAILABLE


def _apply_confidence_caps(
    score: int,
    *,
    level: RecommendationConfidenceLevel,
    policy: RecommendationPriorityPolicy,
) -> tuple[int, list[RecommendationPriorityBasis], list[str]]:
    basis: list[RecommendationPriorityBasis] = [
        RecommendationPriorityBasis.RECOMMENDATION_CONFIDENCE
    ]
    limits: list[str] = []
    capped = score

    if level is RecommendationConfidenceLevel.HIGH:
        return capped, basis, limits

    max_priority = policy.moderate_confidence_max_priority
    if level is RecommendationConfidenceLevel.MODERATE:
        if policy.allows_direct_security_exposure and policy.allows_immediate:
            # Moderate may still reach Immediate for explicit direct-exposure policies.
            max_priority = RecommendationPriority.IMMEDIATE
        else:
            max_priority = policy.moderate_confidence_max_priority
            # Generally cannot be Critical/Immediate unless exposure policy.
            if max_priority is RecommendationPriority.IMMEDIATE and not policy.allows_immediate:
                max_priority = RecommendationPriority.HIGH
    elif level is RecommendationConfidenceLevel.LIMITED:
        max_priority = policy.limited_confidence_max_priority
    else:
        max_priority = policy.unavailable_confidence_max_priority

    max_score = _max_score_for_priority(max_priority)
    if capped > max_score:
        capped = max_score
        basis.append(RecommendationPriorityBasis.CONFIDENCE_CAP)
        limits.append(
            f"Recommendation Confidence {level.value} caps priority at {max_priority.value}."
        )
    return capped, basis, limits


def _max_score_for_priority(priority: RecommendationPriority) -> int:
    if priority is RecommendationPriority.IMMEDIATE:
        return PRIORITY_SCORE_MAX
    if priority is RecommendationPriority.HIGH:
        return BAND_IMMEDIATE_MIN - 1
    if priority is RecommendationPriority.MEDIUM:
        return BAND_HIGH_MIN - 1
    return BAND_MEDIUM_MIN - 1


def _score_within_band(priority: RecommendationPriority, preferred: int) -> int:
    if priority is RecommendationPriority.IMMEDIATE:
        return max(BAND_IMMEDIATE_MIN, min(PRIORITY_SCORE_MAX, preferred))
    if priority is RecommendationPriority.HIGH:
        return max(BAND_HIGH_MIN, min(BAND_IMMEDIATE_MIN - 1, preferred))
    if priority is RecommendationPriority.MEDIUM:
        return max(BAND_MEDIUM_MIN, min(BAND_HIGH_MIN - 1, preferred))
    return max(0, min(BAND_MEDIUM_MIN - 1, preferred))


def _affected_subject_count(
    recommendation: Any,
    supporting: Sequence[Any],
) -> int | None:
    metadata = getattr(recommendation, "metadata", None) or {}
    if isinstance(metadata, Mapping):
        for key in ("affected_subject_count", "subject_count", "file_count"):
            raw = metadata.get(key)
            if raw is not None:
                try:
                    return max(0, int(raw))
                except (TypeError, ValueError):
                    pass
    if supporting:
        return len(supporting)
    return None


def _is_correlation_aware_recommendation(recommendation: Any) -> bool:
    metadata = getattr(recommendation, "metadata", None) or {}
    if isinstance(metadata, Mapping) and str(metadata.get("correlation_aware", "")).lower() in {
        "1",
        "true",
        "yes",
    }:
        return True
    provider_id = str(getattr(recommendation, "provider_id", "") or "")
    return "correlation" in provider_id


def _correlation_signal_count(
    recommendation: Any,
    supporting: Sequence[Any],
) -> int:
    """Diagnostic count only — never used as an unbounded score multiplier."""

    if _is_correlation_aware_recommendation(recommendation):
        return max(0, len(supporting) - 1)
    return 0


def _non_production_context(findings: Sequence[Any]) -> bool:
    markers = ("test", "fixture", "example", "documentation", "docs", "generated", "ci")
    for item in findings:
        assessment = getattr(item, "severity_assessment", None)
        if assessment is not None:
            components = getattr(assessment, "component_summary", None)
            context = None
            if components is not None:
                context = getattr(components, "context_class", None) or getattr(
                    components, "context", None
                )
            if context is None and isinstance(assessment, Mapping):
                summary = assessment.get("component_summary") or {}
                if isinstance(summary, Mapping):
                    context = summary.get("context_class") or summary.get("context")
            if context and str(context).strip().lower() in markers:
                return True
        metadata = getattr(item, "metadata", None) or {}
        if isinstance(metadata, Mapping):
            ctx = str(metadata.get("context_class") or metadata.get("context") or "").lower()
            if ctx in markers:
                return True
            path = str(metadata.get("path") or metadata.get("file_path") or "").lower()
            if any(token in path for token in ("/test/", "/tests/", "/docs/", "/example")):
                return True
    return False


__all__ = [
    "BUCKET_IMMEDIATE_MIN",
    "BUCKET_NEAR_TERM_MIN",
    "apply_recommendation_priority",
    "calibrate_recommendation_priority",
    "presentation_bucket_for_calibrated_score",
    "priority_assessment_to_json",
]
