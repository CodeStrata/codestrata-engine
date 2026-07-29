"""Standard limitations for repository-testing evidence."""

from __future__ import annotations

from codestrata.domain.evidence.repository_testing.enums import (
    RepositoryTestingLimitationCategory,
)
from codestrata.domain.evidence.repository_testing.identifiers import make_limitation_id
from codestrata.domain.evidence.repository_testing.models import (
    RepositoryTestingLimitation,
)

_STANDARD: tuple[tuple[RepositoryTestingLimitationCategory, str], ...] = (
    (
        RepositoryTestingLimitationCategory.REPOSITORY_SNAPSHOT_ONLY,
        "Repository snapshot only.",
    ),
    (
        RepositoryTestingLimitationCategory.TESTS_NOT_EXECUTED,
        "Tests are not executed.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_PASS_FAIL_EVALUATION,
        "Test pass/fail status is not evaluated.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_RUNTIME_COVERAGE,
        "Runtime code coverage is not measured.",
    ),
    (
        RepositoryTestingLimitationCategory.FRAMEWORK_DETECTION_BOUNDED,
        "Framework detection is limited to supported declarations and structural "
        "indicators.",
    ),
    (
        RepositoryTestingLimitationCategory.TEST_TYPE_CONVENTION_BASED,
        "Test-type classification is based on repository conventions and explicit "
        "configuration.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_TEST_EFFECTIVENESS,
        "Test effectiveness and assertion quality are not evaluated.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_TEST_TO_SOURCE_MAPPING,
        "Test-to-production-code coverage is not evaluated.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_REMOTE_CI_HISTORY,
        "Remote CI execution history is not inspected.",
    ),
    (
        RepositoryTestingLimitationCategory.MARKERS_NOT_JUDGED,
        "Disabled or skipped markers are collected without judging whether they "
        "are justified.",
    ),
    (
        RepositoryTestingLimitationCategory.FIXTURE_CONTENT_NOT_EVALUATED,
        "Fixture and test-data content is not evaluated.",
    ),
    (
        RepositoryTestingLimitationCategory.GENERATED_VENDOR_EXCLUSIONS,
        "Generated, vendored, binary, unsupported, or oversized files may be "
        "excluded.",
    ),
    (
        RepositoryTestingLimitationCategory.NO_RELEASE_READINESS,
        "No conclusion about release readiness can be drawn.",
    ),
)


def standard_limitations() -> tuple[RepositoryTestingLimitation, ...]:
    return tuple(
        RepositoryTestingLimitation(
            limitation_id=make_limitation_id(
                category=category.value, summary=summary
            ),
            category=category,
            summary=summary,
        )
        for category, summary in _STANDARD
    )
