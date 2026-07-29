"""Cloud synthesis domain package (Phase 4.7.5)."""

from codestrata.domain.cloud.synthesis.enums import (
    CloudConclusionAudience,
    CloudConclusionKind,
    CloudRecommendationKind,
    CloudSynthesisStatus,
    CloudThemeKind,
    CloudThemeScope,
)
from codestrata.domain.cloud.synthesis.identifiers import (
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.cloud.synthesis.models import (
    CloudConclusion,
    CloudRecommendation,
    CloudSynthesisResult,
    CloudTheme,
)

__all__ = [
    "SYNTHESIS_VERSION",
    "CloudConclusion",
    "CloudConclusionAudience",
    "CloudConclusionKind",
    "CloudRecommendation",
    "CloudRecommendationKind",
    "CloudSynthesisResult",
    "CloudSynthesisStatus",
    "CloudTheme",
    "CloudThemeKind",
    "CloudThemeScope",
    "build_conclusion_id",
    "build_recommendation_id",
    "build_theme_id",
]
