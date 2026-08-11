"""Phase 3 deterministic recommendations domain."""

from codestrata.domain.recommendations.enums import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationSource,
    RecommendationType,
)
from codestrata.domain.recommendations.ids import build_recommendation_id
from codestrata.domain.recommendations.models import (
    RECOMMENDATION_RESULT_VERSION,
    Recommendation,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationResult,
)
from codestrata.domain.recommendations.priority import (
    PriorityCalibrationStatus,
    RecommendationPriorityAssessment,
    RecommendationPriorityBasis,
    RecommendationPriorityComponents,
)
from codestrata.domain.recommendations.recommendation_confidence import (
    RecommendationConfidence,
    RecommendationConfidenceBasis,
    RecommendationConfidenceComponents,
    RecommendationConfidenceDerivationStatus,
    RecommendationConfidenceLevel,
    recommendation_confidence_level_rank,
    recommendation_confidence_to_json,
    min_recommendation_confidence_level,
)

__all__ = [
    "RECOMMENDATION_RESULT_VERSION",
    "PriorityCalibrationStatus",
    "Recommendation",
    "RecommendationAction",
    "RecommendationCategory",
    "RecommendationConfidence",
    "RecommendationConfidenceBasis",
    "RecommendationConfidenceComponents",
    "RecommendationConfidenceDerivationStatus",
    "RecommendationConfidenceLevel",
    "RecommendationEvidence",
    "RecommendationPriority",
    "RecommendationPriorityAssessment",
    "RecommendationPriorityBasis",
    "RecommendationPriorityComponents",
    "RecommendationResult",
    "RecommendationSource",
    "RecommendationType",
    "build_recommendation_id",
    "min_recommendation_confidence_level",
    "recommendation_confidence_level_rank",
    "recommendation_confidence_to_json",
]
