"""Dependency synthesis domain package (Phase 4.4.5)."""

from codestrata.domain.dependency.synthesis.enums import (
    DependencyConclusionAudience,
    DependencyConclusionKind,
    DependencyRecommendationKind,
    DependencySynthesisStatus,
    DependencyThemeKind,
    DependencyThemeScope,
)
from codestrata.domain.dependency.synthesis.identifiers import (
    MANIFEST_FINDING_CONCENTRATION_MIN_SHARE,
    PLUGIN_SHARE_MIN_FOR_THEME,
    SYNTHESIS_VERSION,
    build_concentration_fact_id,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.dependency.synthesis.models import (
    DependencyConcentrationFact,
    DependencyConclusion,
    DependencyRecommendation,
    DependencySynthesisResult,
    DependencyTheme,
)

__all__ = [
    "MANIFEST_FINDING_CONCENTRATION_MIN_SHARE",
    "PLUGIN_SHARE_MIN_FOR_THEME",
    "SYNTHESIS_VERSION",
    "DependencyConcentrationFact",
    "DependencyConclusion",
    "DependencyConclusionAudience",
    "DependencyConclusionKind",
    "DependencyRecommendation",
    "DependencyRecommendationKind",
    "DependencySynthesisResult",
    "DependencySynthesisStatus",
    "DependencyTheme",
    "DependencyThemeKind",
    "DependencyThemeScope",
    "build_concentration_fact_id",
    "build_conclusion_id",
    "build_recommendation_id",
    "build_theme_id",
]
