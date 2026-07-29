"""Test Intelligence pack identifiers (Phase 4.6.3).

``testing.core`` hygiene rules consume AggregatedRepositoryTestingEvidence only.
Human aliases: TEST-001 … TEST-005 map to ``testing.test-00N`` rule IDs
(Shared Rule Platform namespace.kebab form).
"""

from __future__ import annotations

PACK_ID = "testing.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Test Intelligence Core"
PACK_DESCRIPTION = (
    "Test Intelligence SharedRule pack for repository-observable testing "
    "hygiene. Rules consume AggregatedRepositoryTestingEvidence only and "
    "never re-read repository files, execute tests, or measure runtime coverage."
)

RULE_ID_PREFIX = "testing."
RULE_VERSION = "1.0.0"

TAXONOMY_NAMESPACE = "testing"

# Machine IDs (platform-valid). Documented aliases: TEST-001 … TEST-005.
RULE_DISABLED_OR_SKIPPED = "testing.test-001"
RULE_UNCONFIRMED_CANDIDATES = "testing.test-002"
RULE_DECLARED_WITHOUT_OBSERVATION = "testing.test-003"
RULE_OBSERVED_WITHOUT_DECLARATION = "testing.test-004"  # deferred — not registered
RULE_COVERAGE_WITHOUT_CI_INVOCATION = "testing.test-005"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
)

TESTING_RULE_IDS: tuple[str, ...] = HYGIENE_RULE_IDS

DEFERRED_RULE_IDS: tuple[str, ...] = (RULE_OBSERVED_WITHOUT_DECLARATION,)

RULE_ALIAS_TO_ID: dict[str, str] = {
    "TEST-001": RULE_DISABLED_OR_SKIPPED,
    "TEST-002": RULE_UNCONFIRMED_CANDIDATES,
    "TEST-003": RULE_DECLARED_WITHOUT_OBSERVATION,
    "TEST-004": RULE_OBSERVED_WITHOUT_DECLARATION,
    "TEST-005": RULE_COVERAGE_WITHOUT_CI_INVOCATION,
}
