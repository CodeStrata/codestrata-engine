"""Documented deterministic relationships among architecture rule IDs."""

from __future__ import annotations

from codestrata.domain.architecture.conclusions.enums import FindingRelationshipType
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)

# (rule_a, rule_b, relationship_type, reason_code) — unordered pairs normalized later.
RULE_RELATIONSHIP_CATALOG: tuple[tuple[str, str, FindingRelationshipType, str], ...] = (
    (
        RULE_DEPENDENCY_CYCLE,
        RULE_INVALID_DEPENDENCY_DIRECTION,
        FindingRelationshipType.REINFORCES,
        "cycle_and_direction_same_boundary",
    ),
    (
        RULE_DEPENDENCY_CYCLE,
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        FindingRelationshipType.SUPPORTS,
        "coupled_unit_also_in_cycle",
    ),
    (
        RULE_INVALID_DEPENDENCY_DIRECTION,
        RULE_LAYER_BOUNDARY_VIOLATION,
        FindingRelationshipType.OVERLAPS,
        "same_dependency_direction_and_boundary",
    ),
    (
        RULE_FRAMEWORK_LEAKAGE,
        RULE_LAYER_BOUNDARY_VIOLATION,
        FindingRelationshipType.REINFORCES,
        "framework_crosses_independent_boundary",
    ),
    (
        RULE_COMPONENT_CONCENTRATION,
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        FindingRelationshipType.REINFORCES,
        "fanout_and_concentration_same_unit",
    ),
    (
        RULE_ENTERPRISE_STANDARD_MISMATCH,
        RULE_DEPENDENCY_CYCLE,
        FindingRelationshipType.SUPPORTS,
        "enterprise_standard_and_technical_finding",
    ),
    (
        RULE_ENTERPRISE_STANDARD_MISMATCH,
        RULE_INVALID_DEPENDENCY_DIRECTION,
        FindingRelationshipType.SUPPORTS,
        "enterprise_standard_and_technical_finding",
    ),
    (
        RULE_ENTERPRISE_STANDARD_MISMATCH,
        RULE_LAYER_BOUNDARY_VIOLATION,
        FindingRelationshipType.SUPPORTS,
        "enterprise_standard_and_technical_finding",
    ),
    (
        RULE_ENTERPRISE_STANDARD_MISMATCH,
        RULE_FRAMEWORK_LEAKAGE,
        FindingRelationshipType.SUPPORTS,
        "enterprise_standard_and_technical_finding",
    ),
)

# Couplings that stay independent unless shared scope evidence is strong.
INDEPENDENT_BY_DEFAULT: frozenset[tuple[str, str]] = frozenset(
    {
        (RULE_COMPONENT_CONCENTRATION, RULE_DEPENDENCY_CYCLE),
        (RULE_EXCESSIVE_CROSS_MODULE_COUPLING, RULE_FRAMEWORK_LEAKAGE),
        (RULE_DEPENDENCY_CYCLE, RULE_FRAMEWORK_LEAKAGE),
    }
)

# Boundary-integrity family vs coupling family — prefer separate conclusions (Option A).
BOUNDARY_RULES: frozenset[str] = frozenset(
    {
        RULE_DEPENDENCY_CYCLE,
        RULE_INVALID_DEPENDENCY_DIRECTION,
        RULE_LAYER_BOUNDARY_VIOLATION,
        RULE_FRAMEWORK_LEAKAGE,
    }
)
COUPLING_RULES: frozenset[str] = frozenset(
    {
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        RULE_COMPONENT_CONCENTRATION,
    }
)


def catalog_entry(
    rule_a: str,
    rule_b: str,
) -> tuple[FindingRelationshipType, str] | None:
    left, right = sorted((rule_a, rule_b))
    if (left, right) in INDEPENDENT_BY_DEFAULT:
        return None
    for first, second, rel_type, reason in RULE_RELATIONSHIP_CATALOG:
        pair = tuple(sorted((first, second)))
        if pair == (left, right):
            return rel_type, reason
    return None
