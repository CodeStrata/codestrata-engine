"""Cloud assessment section enums (Phase 4.7.1)."""

from __future__ import annotations

from enum import StrEnum


class CloudAssessmentStatus(StrEnum):
    """Explicit Cloud assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class CloudCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class CloudCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CloudLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    FOUNDATION_ONLY = "foundation-only"
    CLOUD_ANALYSIS_NOT_IMPLEMENTED = "cloud-analysis-not-implemented"
    PROVIDER_DETECTION_NOT_IMPLEMENTED = "provider-detection-not-implemented"
    CONFIG_EXTERNALIZATION_NOT_EVALUATED = "config-externalization-not-evaluated"
    STATELESSNESS_NOT_EVALUATED = "statelessness-not-evaluated"
    PORTABILITY_NOT_EVALUATED = "portability-not-evaluated"
    CONTAINER_READINESS_NOT_EVALUATED = "container-readiness-not-evaluated"
    MANAGED_SERVICE_COMPATIBILITY_NOT_EVALUATED = "managed-service-compatibility-not-evaluated"
    DEPLOYMENT_AUTOMATION_NOT_EVALUATED = "deployment-automation-not-evaluated"
    NO_CLOUD_READINESS_CONCLUSION = "no-cloud-readiness-conclusion"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    OTHER = "other"


class CloudTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    PACK_TO_RULE = "pack_to_rule"
