"""Performance Intelligence domain package (Phase 4.9.1)."""

from codestrata.domain.performance.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    PERFORMANCE_RULE_IDS,
    RULE_ALIAS_TO_ID,
    RULE_ID_PREFIX,
    TAXONOMY_NAMESPACE,
)
from codestrata.domain.performance.taxonomy import (
    PERFORMANCE_CATEGORIES,
    PerformanceCategory,
    coerce_performance_category,
)

__all__ = [
    "DEFERRED_RULE_IDS",
    "HYGIENE_RULE_IDS",
    "PACK_DESCRIPTION",
    "PACK_ID",
    "PACK_TITLE",
    "PACK_VERSION",
    "PERFORMANCE_CATEGORIES",
    "PERFORMANCE_RULE_IDS",
    "RULE_ALIAS_TO_ID",
    "RULE_ID_PREFIX",
    "TAXONOMY_NAMESPACE",
    "PerformanceCategory",
    "coerce_performance_category",
]
