"""Dependency Intelligence pack identifiers (Phase 4.4.1 / 4.4.3)."""

from __future__ import annotations

PACK_ID = "dependency.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "Dependency Intelligence Core"
PACK_DESCRIPTION = (
    "Dependency Intelligence SharedRule pack for repository-provable dependency "
    "declaration hygiene. Consumes Dependency Evidence only; no registry, CVE, "
    "or transitive resolution."
)

RULE_ID_PREFIX = "dependency."

TAXONOMY_NAMESPACE = "dependency"

RULE_VERSION = "1.0.0"

RULE_UNRESOLVED_VERSION = "dependency.unresolved-version"
RULE_MUTABLE_VERSION = "dependency.mutable-version"
RULE_UNBOUNDED_REQUIREMENT = "dependency.unbounded-requirement"
RULE_CONFLICTING_EXACT_VERSIONS = "dependency.conflicting-exact-versions"
RULE_DUPLICATE_DECLARATION = "dependency.duplicate-declaration"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_UNRESOLVED_VERSION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
)
