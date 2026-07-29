"""Deterministic priority mapping from finding severity."""

from __future__ import annotations

from codestrata.domain.findings import FindingSeverity
from codestrata.domain.recommendations import RecommendationPriority


def priority_from_finding_severity(severity: FindingSeverity) -> RecommendationPriority:
    """Map finding severity to recommendation priority.

    CRITICAL → IMMEDIATE, HIGH → HIGH, MEDIUM → MEDIUM, LOW/INFO → LOW.
    Individual providers may override when justified.
    """

    if severity is FindingSeverity.CRITICAL:
        return RecommendationPriority.IMMEDIATE
    if severity is FindingSeverity.HIGH:
        return RecommendationPriority.HIGH
    if severity is FindingSeverity.MEDIUM:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW
