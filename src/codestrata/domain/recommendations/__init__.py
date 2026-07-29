"""Phase 3 deterministic recommendations domain."""

from codestrata.domain.recommendations.enums import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationSource,
)
from codestrata.domain.recommendations.ids import build_recommendation_id
from codestrata.domain.recommendations.models import (
    RECOMMENDATION_RESULT_VERSION,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationResult,
)

__all__ = [
    "RECOMMENDATION_RESULT_VERSION",
    "Recommendation",
    "RecommendationAction",
    "RecommendationCategory",
    "RecommendationEvidence",
    "RecommendationPriority",
    "RecommendationResult",
    "RecommendationSource",
    "build_recommendation_id",
]
