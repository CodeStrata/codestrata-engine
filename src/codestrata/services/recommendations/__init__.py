"""Deterministic Phase 3 Recommendation Engine services."""

from codestrata.services.recommendations.artifacts import (
    RECOMMENDATIONS_FILENAME,
    RecommendationsArtifactWriteResult,
    format_recommendation_console_summary,
    write_recommendations_artifact,
)
from codestrata.services.recommendations.context import RecommendationContext
from codestrata.services.recommendations.engine import RecommendationEngine
from codestrata.services.recommendations.priority import priority_from_finding_severity
from codestrata.services.recommendations.protocol import RecommendationProvider
from codestrata.services.recommendations.providers import builtin_recommendation_providers

__all__ = [
    "RECOMMENDATIONS_FILENAME",
    "RecommendationContext",
    "RecommendationEngine",
    "RecommendationProvider",
    "RecommendationsArtifactWriteResult",
    "builtin_recommendation_providers",
    "format_recommendation_console_summary",
    "priority_from_finding_severity",
    "write_recommendations_artifact",
]
