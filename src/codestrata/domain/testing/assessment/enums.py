"""Test assessment section enums (Phase 4.6.1)."""

from __future__ import annotations

from enum import StrEnum


class TestAssessmentStatus(StrEnum):
    """Explicit Test assessment section status."""

    __test__ = False

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class TestCoverageAreaStatus(StrEnum):
    __test__ = False

    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class TestCoverageMaturity(StrEnum):
    __test__ = False

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class TestLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    __test__ = False

    FOUNDATION_ONLY = "foundation-only"
    TEST_ANALYSIS_NOT_IMPLEMENTED = "test-analysis-not-implemented"
    TEST_DISCOVERY_NOT_IMPLEMENTED = "test-discovery-not-implemented"
    FRAMEWORK_DETECTION_NOT_IMPLEMENTED = "framework-detection-not-implemented"
    BUILD_INSPECTION_NOT_IMPLEMENTED = "build-inspection-not-implemented"
    TEST_EXECUTION_NOT_PERFORMED = "test-execution-not-performed"
    COVERAGE_NOT_MEASURED = "coverage-not-measured"
    DISABLED_TEST_DETECTION_NOT_IMPLEMENTED = (
        "disabled-test-detection-not-implemented"
    )
    TEST_TO_SOURCE_MAPPING_NOT_IMPLEMENTED = (
        "test-to-source-mapping-not-implemented"
    )
    CI_INSPECTION_NOT_IMPLEMENTED = "ci-inspection-not-implemented"
    MUTATION_TESTING_NOT_EVALUATED = "mutation-testing-not-evaluated"
    NO_TEST_QUALITY_CONCLUSION = "no-test-quality-conclusion"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    OTHER = "other"


class TestTraceabilityRelation(StrEnum):
    __test__ = False

    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    PACK_TO_RULE = "pack_to_rule"
