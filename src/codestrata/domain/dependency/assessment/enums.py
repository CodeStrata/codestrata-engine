"""Dependency assessment section enums (Phase 4.4.1)."""

from __future__ import annotations

from enum import StrEnum


class DependencyAssessmentStatus(StrEnum):
    """Explicit dependency assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class DependencyCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class DependencyCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class DependencyLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    STATIC_ANALYSIS_ONLY = "static-analysis-only"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    EVIDENCE_PROVIDERS_UNAVAILABLE = "evidence-providers-unavailable"
    MANIFEST_PARSING_NOT_OWNED = "manifest-parsing-not-owned"
    EXTERNAL_REGISTRY_NOT_QUERIED = "external-registry-not-queried"
    CVE_DATA_NOT_ASSESSED = "cve-data-not-assessed"
    LICENSE_NOT_ASSESSED = "license-not-assessed"
    VERSION_FRESHNESS_NOT_ASSESSED = "version-freshness-not-assessed"
    ENTERPRISE_CONTEXT_UNAVAILABLE = "enterprise-context-unavailable"
    BUSINESS_IMPACT_UNKNOWN = "business-impact-unknown"
    PROVIDER_FAILURE = "provider-failure"
    RULE_FAILURE = "rule-failure"
    OTHER = "other"


class DependencyTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_MANIFEST = "section_to_manifest"
    SECTION_TO_HOTSPOT = "section_to_hotspot"
    FINDING_TO_EVIDENCE = "finding_to_evidence"
    FINDING_TO_TAXONOMY = "finding_to_taxonomy"
    COVERAGE_TO_PROVIDER = "coverage_to_provider"
    PACK_TO_RULE = "pack_to_rule"
    HOTSPOT_TO_FINDING = "hotspot_to_finding"
    MANIFEST_TO_EVIDENCE = "manifest_to_evidence"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    CONCLUSION_TO_THEME = "conclusion_to_theme"
    CONCLUSION_TO_FINDING = "conclusion_to_finding"
    CONCLUSION_TO_HOTSPOT = "conclusion_to_hotspot"
    CONCLUSION_TO_MANIFEST = "conclusion_to_manifest"
    CONCLUSION_TO_DIAGNOSTIC = "conclusion_to_diagnostic"
    RECOMMENDATION_TO_CONCLUSION = "recommendation_to_conclusion"


class DependencySourceRole(StrEnum):
    """Inventory source-role partition (not engineering DependencyRole)."""

    PRODUCTION = "production"
    TEST = "test"
    UNKNOWN = "unknown"
