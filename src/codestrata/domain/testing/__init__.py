"""Test Intelligence domain (Phase 4.6.1).

Taxonomy, pack identity, and analytically empty assessment section contracts.
No test discovery, framework detection, rules, or findings in this phase.
"""

from codestrata.domain.testing.ids import (
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_ID_PREFIX,
    TAXONOMY_NAMESPACE,
    TESTING_RULE_IDS,
)
from codestrata.domain.testing.taxonomy import (
    TEST_CATEGORIES,
    TestCategory,
    coerce_test_category,
)

__all__ = [
    "PACK_DESCRIPTION",
    "PACK_ID",
    "PACK_TITLE",
    "PACK_VERSION",
    "RULE_ID_PREFIX",
    "TAXONOMY_NAMESPACE",
    "TEST_CATEGORIES",
    "TESTING_RULE_IDS",
    "TestCategory",
    "coerce_test_category",
]
