"""Technical debt assessment section enums (Phase 4.3.1)."""

from __future__ import annotations

from enum import StrEnum


class TechnicalDebtAssessmentStatus(StrEnum):
    """Explicit technical debt assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class TechnicalDebtCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class TechnicalDebtCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class TechnicalDebtLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    STATIC_ANALYSIS_ONLY = "static-analysis-only"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    EVIDENCE_PROVIDERS_UNAVAILABLE = "evidence-providers-unavailable"
    GENERATED_SOURCE_EXCLUDED = "generated-source-excluded"
    WORKSPACE_CONTENT_EXCLUDED = "workspace-content-excluded"
    RUNTIME_BEHAVIOR_NOT_OBSERVED = "runtime-behavior-not-observed"
    ENTERPRISE_CONTEXT_UNAVAILABLE = "enterprise-context-unavailable"
    FINANCIAL_COST_NOT_ASSESSED = "financial-cost-not-assessed"
    EFFORT_NOT_ASSESSED = "effort-not-assessed"
    BUSINESS_IMPACT_UNKNOWN = "business-impact-unknown"
    PROVIDER_FAILURE = "provider-failure"
    RULE_FAILURE = "rule-failure"
    OTHER = "other"


class TechnicalDebtTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    FINDING_TO_EVIDENCE = "finding_to_evidence"
    FINDING_TO_TAXONOMY = "finding_to_taxonomy"
    COVERAGE_TO_PROVIDER = "coverage_to_provider"
    PACK_TO_RULE = "pack_to_rule"
    SECTION_TO_HOTSPOT = "section_to_hotspot"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    CONCLUSION_TO_FINDING = "conclusion_to_finding"
    CONCLUSION_TO_THEME = "conclusion_to_theme"
    CONCLUSION_TO_HOTSPOT = "conclusion_to_hotspot"
    RECOMMENDATION_TO_CONCLUSION = "recommendation_to_conclusion"


class TechnicalDebtSourceRole(StrEnum):
    """Assessment inventory source-role partition (Phase 4.3.4A)."""

    PRODUCTION = "production"
    TEST = "test"
    UNKNOWN = "unknown"
