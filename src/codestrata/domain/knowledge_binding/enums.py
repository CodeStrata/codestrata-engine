"""Repository-to-knowledge binding contracts.

Bindings are a separate immutable result linking Repository Graph observations
to Engineering Knowledge Graph concepts. They never mutate either source graph
and are designed as direct input for a future Assessment Graph.
"""

from __future__ import annotations

from enum import StrEnum


class KnowledgeBindingType(StrEnum):
    """Semantic role of a repository-to-knowledge binding."""

    USES_CONCEPT = "uses_concept"


class KnowledgeMatchingStrategy(StrEnum):
    """Deterministic strategy that produced a binding.

    New strategies (coordinate maps, version-aware rules, etc.) can be added
    without changing the binding result contract.
    """

    EXACT_CANONICAL_KEY = "exact_canonical_key"
    EXACT_ALIAS = "exact_alias"


class KnowledgeObservationKind(StrEnum):
    """Which Repository Graph observation field produced a candidate key."""

    DEPENDENCY_NAME = "dependency_name"
    FILE_LANGUAGE = "file_language"
    MODULE_BUILD_SYSTEM = "module_build_system"
