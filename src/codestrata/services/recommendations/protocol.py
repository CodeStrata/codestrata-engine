"""Recommendation provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from codestrata.domain.findings import Finding
from codestrata.domain.recommendations import Recommendation
from codestrata.services.recommendations.context import RecommendationContext


@runtime_checkable
class RecommendationProvider(Protocol):
    """Deterministic finding → recommendation mapping."""

    def id(self) -> str:
        """Stable provider identity."""

    def supported_finding_rule_ids(self) -> frozenset[str]:
        """Finding rule IDs this provider may handle."""

    def recommend(
        self,
        finding: Finding,
        context: RecommendationContext,
    ) -> tuple[Recommendation, ...]:
        """Return zero or more recommendations for ``finding`` without AI."""
