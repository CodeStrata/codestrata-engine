"""Deterministic recommendation priority helpers.

``priority_from_finding_severity`` remains a compatibility fallback for providers
that still seed an initial priority before Slice 5.14 calibration runs. Canonical
priority is produced by ``apply_recommendation_priority`` after Recommendation
Confidence is known.
"""

from __future__ import annotations

from codestrata.domain.findings import FindingSeverity
from codestrata.domain.recommendations import RecommendationPriority


def priority_from_finding_severity(severity: FindingSeverity) -> RecommendationPriority:
    """Compatibility seed mapping — not the calibrated priority authority.

    CRITICAL → IMMEDIATE, HIGH → HIGH, MEDIUM → MEDIUM, LOW/INFO → LOW.
    Slice 5.14 recalibrates after Recommendation Confidence is derived.
    """

    if severity is FindingSeverity.CRITICAL:
        return RecommendationPriority.IMMEDIATE
    if severity is FindingSeverity.HIGH:
        return RecommendationPriority.HIGH
    if severity is FindingSeverity.MEDIUM:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW
