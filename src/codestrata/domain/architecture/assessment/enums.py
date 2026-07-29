"""Architecture assessment section enums (Phase 4.2.4)."""

from __future__ import annotations

from enum import StrEnum


class ArchitectureAssessmentStatus(StrEnum):
    """Explicit architecture assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class CoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ArchitectureLimitationCategory(StrEnum):
    STATIC_ANALYSIS_ONLY = "static-analysis-only"
    PARTIAL_LANGUAGE_SUPPORT = "partial-language-support"
    PARTIAL_CLASSIFICATION = "partial-classification"
    FRAMEWORK_DETECTION_LIMITED = "framework-detection-limited"
    BUILD_METADATA_LIMITED = "build-metadata-limited"
    GENERATED_SOURCE_EXCLUDED = "generated-source-excluded"
    RUNTIME_BEHAVIOR_NOT_OBSERVED = "runtime-behavior-not-observed"
    ENTERPRISE_CONTEXT_UNAVAILABLE = "enterprise-context-unavailable"
    POSITIVE_EVIDENCE_UNAVAILABLE = "positive-evidence-unavailable"
    PROVIDER_FAILURE = "provider-failure"
    RULE_FAILURE = "rule-failure"
    CONCLUSION_POLICY_FAILURE = "conclusion-policy-failure"
    CONCLUSIONS_DISABLED = "conclusions-disabled"
    OTHER = "other"


class TraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION_GROUP = "section_to_recommendation_group"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    FINDING_TO_EVIDENCE = "finding_to_evidence"
    CONCLUSION_TO_FINDING = "conclusion_to_finding"
    RECOMMENDATION_GROUP_TO_FINDING = "recommendation_group_to_finding"
    RECOMMENDATION_GROUP_TO_RECOMMENDATION = "recommendation_group_to_recommendation"
    COVERAGE_TO_PROVIDER = "coverage_to_provider"
    PACK_TO_RULE = "pack_to_rule"
