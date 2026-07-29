"""Test synthesis enums (Phase 4.6.5)."""

from __future__ import annotations

from enum import StrEnum


class TestThemeKind(StrEnum):
    """Bounded theme kinds derived from Test assessment inventory."""

    __test__ = False

    TESTING_HYGIENE_LANDSCAPE = "testing_hygiene_landscape"
    RULE_EXECUTION_COVERAGE = "rule_execution_coverage"
    DISABLED_OR_SKIPPED_TESTS = "disabled_or_skipped_tests"
    TEST_DISCOVERY_CONFIDENCE = "test_discovery_confidence"
    FRAMEWORK_DECLARATION_CONSISTENCY = "framework_declaration_consistency"
    COVERAGE_AND_CI_ALIGNMENT = "coverage_and_ci_alignment"
    NO_HYGIENE_FINDINGS = "no_hygiene_findings"
    UNSUPPORTED_ANALYSIS_SCOPE = "unsupported_analysis_scope"


class TestThemeScope(StrEnum):
    __test__ = False

    REPOSITORY = "repository"
    COVERAGE = "coverage"
    HYGIENE = "hygiene"
    STATUS = "status"


class TestConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    __test__ = False

    TESTING_HYGIENE_LANDSCAPE_IDENTIFIED = "testing_hygiene_landscape_identified"
    RULE_EXECUTION_SUMMARY = "rule_execution_summary"
    DISABLED_OR_SKIPPED_TESTS_OBSERVED = "disabled_or_skipped_tests_observed"
    TEST_DISCOVERY_UNCERTAINTY_OBSERVED = "test_discovery_uncertainty_observed"
    FRAMEWORK_DECLARATION_GAP_OBSERVED = "framework_declaration_gap_observed"
    COVERAGE_WITHOUT_CI_OBSERVED = "coverage_without_ci_observed"
    NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = "no_hygiene_findings_in_supported_scope"
    UNSUPPORTED_TEST_ANALYSIS_SCOPE = "unsupported_test_analysis_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SYNTHESIS_DISABLED = "synthesis_disabled"


class TestConclusionAudience(StrEnum):
    __test__ = False

    REPOSITORY = "repository"
    HYGIENE = "hygiene"
    COVERAGE = "coverage"
    STATUS = "status"


class TestRecommendationKind(StrEnum):
    """Bounded recommendation kinds linked to conclusions."""

    __test__ = False

    REVIEW_DISABLED_OR_SKIPPED_TESTS = "review_disabled_or_skipped_tests"
    IMPROVE_TEST_DISCOVERY_SIGNALING = "improve_test_discovery_signaling"
    ALIGN_FRAMEWORK_DECLARATION_AND_OBSERVATION = "align_framework_declaration_and_observation"
    ALIGN_COVERAGE_CONFIG_WITH_CI = "align_coverage_config_with_ci"
    ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = (
        "acknowledge_no_hygiene_findings_in_supported_scope"
    )
    ACKNOWLEDGE_UNSUPPORTED_TEST_ANALYSIS_SCOPE = "acknowledge_unsupported_test_analysis_scope"


class TestSynthesisStatus(StrEnum):
    __test__ = False

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
