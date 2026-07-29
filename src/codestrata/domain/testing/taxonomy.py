"""Test Intelligence taxonomy (Phase 4.6.1).

Repository-observable testing categories for future rules and assessment
metadata. These values are methodology identifiers only.

This phase does not discover tests, detect frameworks, measure coverage, or
emit findings for any category.
"""

from __future__ import annotations

from enum import StrEnum


class TestCategory(StrEnum):
    """Bounded Test Intelligence categories.

    Serialized values use the ``testing.<category>`` namespace.
    """

    __test__ = False

    TEST_PRESENCE = "testing.test_presence"
    TEST_STRUCTURE = "testing.test_structure"
    FRAMEWORK = "testing.framework"
    UNIT_TESTING = "testing.unit_testing"
    INTEGRATION_TESTING = "testing.integration_testing"
    END_TO_END_TESTING = "testing.end_to_end_testing"
    CONTRACT_TESTING = "testing.contract_testing"
    SMOKE_TESTING = "testing.smoke_testing"
    PERFORMANCE_TESTING = "testing.performance_testing"
    TEST_DISTRIBUTION = "testing.test_distribution"
    TEST_ISOLATION = "testing.test_isolation"
    DISABLED_TEST = "testing.disabled_test"
    IGNORED_TEST = "testing.ignored_test"
    FLAKY_TEST_INDICATOR = "testing.flaky_test_indicator"
    TEST_CONFIGURATION = "testing.test_configuration"
    FIXTURE = "testing.fixture"
    MOCKING = "testing.mocking"
    COVERAGE_CONFIGURATION = "testing.coverage_configuration"
    BUILD_INTEGRATION = "testing.build_integration"
    CONTINUOUS_INTEGRATION = "testing.continuous_integration"
    MAINTAINABILITY = "testing.maintainability"
    MODERNIZATION_SAFETY_NET = "testing.modernization_safety_net"
    MISCELLANEOUS = "testing.miscellaneous"
    UNKNOWN = "testing.unknown"


TEST_CATEGORIES: tuple[TestCategory, ...] = tuple(TestCategory)


def coerce_test_category(value: object) -> TestCategory:
    """Map a raw taxonomy value to a category, defaulting unknown inputs safely."""

    if isinstance(value, TestCategory):
        return value
    text = str(value or "").strip()
    if not text:
        return TestCategory.UNKNOWN
    try:
        return TestCategory(text)
    except ValueError:
        pass
    bare = text if text.startswith("testing.") else f"testing.{text}"
    try:
        return TestCategory(bare)
    except ValueError:
        return TestCategory.UNKNOWN
