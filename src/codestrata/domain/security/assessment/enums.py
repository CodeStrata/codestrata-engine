"""Security assessment section enums (Phase 4.5.1)."""

from __future__ import annotations

from enum import StrEnum


class SecurityAssessmentStatus(StrEnum):
    """Explicit security assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class SecurityCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class SecurityCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SecurityLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    SECURITY_EVIDENCE_NOT_IMPLEMENTED = "security-evidence-not-implemented"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    NO_RUNTIME_ANALYSIS = "no-runtime-analysis"
    NO_EXTERNAL_VULNERABILITY_METADATA = "no-external-vulnerability-metadata"
    NO_PACKAGE_REGISTRY_QUERY = "no-package-registry-query"
    NO_SAST = "no-sast"
    NO_DATA_FLOW_ANALYSIS = "no-data-flow-analysis"
    NO_GIT_HISTORY_ANALYSIS = "no-git-history-analysis"
    ENTERPRISE_CONTEXT_UNAVAILABLE = "enterprise-context-unavailable"
    BUSINESS_IMPACT_UNKNOWN = "business-impact-unknown"
    FOUNDATION_ONLY = "foundation-only"
    OTHER = "other"


class SecurityTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_HOTSPOT = "section_to_hotspot"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    FINDING_TO_EVIDENCE = "finding_to_evidence"
    FINDING_TO_TAXONOMY = "finding_to_taxonomy"
    PACK_TO_RULE = "pack_to_rule"
    HOTSPOT_TO_FINDING = "hotspot_to_finding"
    THEME_TO_CONCLUSION = "theme_to_conclusion"
    CONCLUSION_TO_RECOMMENDATION = "conclusion_to_recommendation"


class SecuritySourceRole(StrEnum):
    """Inventory source-role partition for Security Findings."""

    PRODUCTION = "production"
    TEST = "test"
    UNKNOWN = "unknown"
