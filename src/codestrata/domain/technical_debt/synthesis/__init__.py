"""Technical Debt synthesis domain package (Phase 4.3.5)."""

from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
    TechnicalDebtConclusionKind,
    TechnicalDebtSynthesisStatus,
)
from codestrata.domain.technical_debt.synthesis.identifiers import (
    HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE,
    PACKAGE_CONCENTRATION_MIN_SHARE,
    POLICY_COMPLEXITY_PRESENT,
    POLICY_DISABLED,
    POLICY_HOTSPOT_CONCENTRATION,
    POLICY_MULTI_RULE_HOTSPOTS,
    POLICY_NO_PRODUCTION,
    POLICY_PACKAGE_CONCENTRATION,
    POLICY_PARTIAL_COVERAGE,
    POLICY_TEST_MAINTAINABILITY,
    SYNTHESIS_VERSION,
    build_concentration_fact_id,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
    theme_policy_id,
)
from codestrata.domain.technical_debt.synthesis.models import (
    TechnicalDebtConcentrationFact,
    TechnicalDebtConclusion,
    TechnicalDebtRecommendation,
    TechnicalDebtSynthesisResult,
    TechnicalDebtTheme,
)

__all__ = [
    "HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE",
    "PACKAGE_CONCENTRATION_MIN_SHARE",
    "POLICY_COMPLEXITY_PRESENT",
    "POLICY_DISABLED",
    "POLICY_HOTSPOT_CONCENTRATION",
    "POLICY_MULTI_RULE_HOTSPOTS",
    "POLICY_NO_PRODUCTION",
    "POLICY_PACKAGE_CONCENTRATION",
    "POLICY_PARTIAL_COVERAGE",
    "POLICY_TEST_MAINTAINABILITY",
    "SYNTHESIS_VERSION",
    "TechnicalDebtConcentrationFact",
    "TechnicalDebtConclusion",
    "TechnicalDebtConclusionAudience",
    "TechnicalDebtConclusionKind",
    "TechnicalDebtRecommendation",
    "TechnicalDebtSynthesisResult",
    "TechnicalDebtSynthesisStatus",
    "TechnicalDebtTheme",
    "build_concentration_fact_id",
    "build_conclusion_id",
    "build_recommendation_id",
    "build_theme_id",
    "theme_policy_id",
]
