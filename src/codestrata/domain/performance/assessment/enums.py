"""Performance assessment section enums (Phase 4.9.1)."""

from __future__ import annotations

from enum import StrEnum


class PerformanceAssessmentStatus(StrEnum):
    """Explicit Performance assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class PerformanceCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class PerformanceCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class PerformanceLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    FOUNDATION_ONLY = "foundation-only"
    PERFORMANCE_ANALYSIS_NOT_IMPLEMENTED = "performance-analysis-not-implemented"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    NO_PERFORMANCE_CONCLUSION = "no-performance-conclusion"
    INEFFICIENT_DATA_ACCESS_NOT_EVALUATED = "inefficient-data-access-not-evaluated"
    BLOCKING_OPERATIONS_NOT_EVALUATED = "blocking-operations-not-evaluated"
    UNBOUNDED_COLLECTION_PROCESSING_NOT_EVALUATED = "unbounded-collection-processing-not-evaluated"
    EXCESSIVE_RESOURCE_CREATION_NOT_EVALUATED = "excessive-resource-creation-not-evaluated"
    CACHING_NOT_EVALUATED = "caching-not-evaluated"
    BATCHING_PAGINATION_NOT_EVALUATED = "batching-pagination-not-evaluated"
    CONCURRENCY_NOT_EVALUATED = "concurrency-not-evaluated"
    RESOURCE_MANAGEMENT_NOT_EVALUATED = "resource-management-not-evaluated"
    FRONTEND_RENDERING_BUNDLE_NOT_EVALUATED = "frontend-rendering-bundle-not-evaluated"
    OBSERVABILITY_PROFILING_NOT_EVALUATED = "observability-profiling-not-evaluated"
    CONFIGURATION_CONTROLS_NOT_EVALUATED = "configuration-controls-not-evaluated"
    SERIALIZATION_NOT_EVALUATED = "serialization-not-evaluated"
    HOT_PATH_COUPLING_NOT_EVALUATED = "hot-path-coupling-not-evaluated"
    OTHER = "other"


class PerformanceTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    PACK_TO_RULE = "pack_to_rule"
