"""Performance synthesis enums (Phase 4.9.5)."""

from __future__ import annotations

from enum import StrEnum


class PerformanceThemeKind(StrEnum):
    """Bounded theme kinds derived from Performance assessment inventory."""

    PERFORMANCE_HYGIENE_LANDSCAPE = "performance_hygiene_landscape"
    RULE_EXECUTION_COVERAGE = "rule_execution_coverage"
    DATA_ACCESS_FOUNDATIONS = "data_access_foundations"
    BLOCKING_OPERATIONS = "blocking_operations"
    CACHING_FOUNDATIONS = "caching_foundations"
    CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING = "concurrency_and_asynchronous_processing"
    RESOURCE_MANAGEMENT = "resource_management"
    FRONTEND_PERFORMANCE_CONTROLS = "frontend_performance_controls"
    PERFORMANCE_OBSERVABILITY_AND_PROFILING = "performance_observability_and_profiling"
    CONFIGURATION_CONTROLS = "configuration_controls"
    BROAD_PERFORMANCE_FOUNDATIONS = "broad_performance_foundations"
    LIMITED_SUPPORTING_CONTROLS = "limited_supporting_controls"
    NO_PERFORMANCE_FINDINGS = "no_performance_findings"
    UNSUPPORTED_ANALYSIS_SCOPE = "unsupported_analysis_scope"


class PerformanceThemeScope(StrEnum):
    REPOSITORY = "repository"
    COVERAGE = "coverage"
    HYGIENE = "hygiene"
    STATUS = "status"


class PerformanceConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    PERFORMANCE_HYGIENE_LANDSCAPE_IDENTIFIED = "performance_hygiene_landscape_identified"
    RULE_EXECUTION_SUMMARY = "rule_execution_summary"
    DATA_ACCESS_FOUNDATIONS_OBSERVED = "data_access_foundations_observed"
    BLOCKING_OPERATIONS_OBSERVED = "blocking_operations_observed"
    CACHING_FOUNDATIONS_OBSERVED = "caching_foundations_observed"
    CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_OBSERVED = (
        "concurrency_and_asynchronous_processing_observed"
    )
    RESOURCE_MANAGEMENT_OBSERVED = "resource_management_observed"
    FRONTEND_PERFORMANCE_CONTROLS_OBSERVED = "frontend_performance_controls_observed"
    PERFORMANCE_OBSERVABILITY_AND_PROFILING_OBSERVED = (
        "performance_observability_and_profiling_observed"
    )
    CONFIGURATION_CONTROLS_OBSERVED = "configuration_controls_observed"
    BROAD_PERFORMANCE_FOUNDATIONS_OBSERVED = "broad_performance_foundations_observed"
    LIMITED_SUPPORTING_CONTROLS_OBSERVED = "limited_supporting_controls_observed"
    NO_PERFORMANCE_FINDINGS_IN_SUPPORTED_SCOPE = "no_performance_findings_in_supported_scope"
    UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE = "unsupported_performance_analysis_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SYNTHESIS_DISABLED = "synthesis_disabled"


class PerformanceConclusionAudience(StrEnum):
    REPOSITORY = "repository"
    HYGIENE = "hygiene"
    COVERAGE = "coverage"
    STATUS = "status"


class PerformanceRecommendationKind(StrEnum):
    """Bounded observation-oriented recommendation kinds."""

    REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS = "review_data_access_foundation_signals"
    REVIEW_BLOCKING_OPERATION_SIGNALS = "review_blocking_operation_signals"
    REVIEW_CACHING_FOUNDATION_SIGNALS = "review_caching_foundation_signals"
    REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS = (
        "review_concurrency_and_asynchronous_processing_signals"
    )
    REVIEW_RESOURCE_MANAGEMENT_SIGNALS = "review_resource_management_signals"
    REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS = "review_frontend_performance_control_signals"
    VALIDATE_OBSERVED_PERFORMANCE_OBSERVABILITY_SIGNALS = (
        "validate_observed_performance_observability_signals"
    )
    VALIDATE_OBSERVED_CONFIGURATION_CONTROLS = "validate_observed_configuration_controls"
    REVIEW_BROAD_PERFORMANCE_FOUNDATIONS = "review_broad_performance_foundations"
    REVIEW_LIMITED_SUPPORTING_CONTROLS = "review_limited_supporting_controls"
    ACKNOWLEDGE_NO_PERFORMANCE_FINDINGS_IN_SUPPORTED_SCOPE = (
        "acknowledge_no_performance_findings_in_supported_scope"
    )
    ACKNOWLEDGE_UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE = (
        "acknowledge_unsupported_performance_analysis_scope"
    )


class PerformanceSynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
