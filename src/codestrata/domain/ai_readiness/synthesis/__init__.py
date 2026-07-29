"""AI Readiness synthesis domain package (Phase 4.8.5)."""

from codestrata.domain.ai_readiness.synthesis.enums import (
    AiReadinessConclusionAudience,
    AiReadinessConclusionKind,
    AiReadinessRecommendationKind,
    AiReadinessSynthesisStatus,
    AiReadinessThemeKind,
    AiReadinessThemeScope,
)
from codestrata.domain.ai_readiness.synthesis.identifiers import (
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.ai_readiness.synthesis.models import (
    AiReadinessConclusion,
    AiReadinessRecommendation,
    AiReadinessSynthesisResult,
    AiReadinessTheme,
)

__all__ = [
    "SYNTHESIS_VERSION",
    "AiReadinessConclusion",
    "AiReadinessConclusionAudience",
    "AiReadinessConclusionKind",
    "AiReadinessRecommendation",
    "AiReadinessRecommendationKind",
    "AiReadinessSynthesisResult",
    "AiReadinessSynthesisStatus",
    "AiReadinessTheme",
    "AiReadinessThemeKind",
    "AiReadinessThemeScope",
    "build_conclusion_id",
    "build_recommendation_id",
    "build_theme_id",
]
