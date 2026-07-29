"""Test synthesis domain package (Phase 4.6.5)."""

from codestrata.domain.testing.synthesis.enums import (
    TestConclusionAudience,
    TestConclusionKind,
    TestRecommendationKind,
    TestSynthesisStatus,
    TestThemeKind,
    TestThemeScope,
)
from codestrata.domain.testing.synthesis.identifiers import (
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.testing.synthesis.models import (
    TestConclusion,
    TestingSynthesisResult,
    TestRecommendation,
    TestTheme,
)

__all__ = [
    "SYNTHESIS_VERSION",
    "TestConclusion",
    "TestConclusionAudience",
    "TestConclusionKind",
    "TestRecommendation",
    "TestRecommendationKind",
    "TestSynthesisStatus",
    "TestTheme",
    "TestThemeKind",
    "TestThemeScope",
    "TestingSynthesisResult",
    "build_conclusion_id",
    "build_recommendation_id",
    "build_theme_id",
]
