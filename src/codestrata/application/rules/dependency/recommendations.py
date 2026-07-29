"""Concise factual remediation text for Dependency hygiene rules."""

from __future__ import annotations

from codestrata.domain.dependency.ids import (
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_UNRESOLVED_VERSION,
)

_REMEDIATIONS: dict[str, str] = {
    RULE_UNRESOLVED_VERSION: (
        "Define or replace the unresolved local version expression so the "
        "declaration states a concrete, locally resolvable version. This finding "
        "does not claim the build fails."
    ),
    RULE_MUTABLE_VERSION: (
        "Replace the mutable version expression with an exact, pinned version so "
        "resolution cannot select a changing artifact over time."
    ),
    RULE_UNBOUNDED_REQUIREMENT: (
        "Add an explicit version specifier to the Python dependency declaration "
        "so the selected version is constrained by the manifest."
    ),
    RULE_CONFLICTING_EXACT_VERSIONS: (
        "Align the conflicting exact version declarations in the same manifest "
        "and resolution context so only one exact version remains."
    ),
    RULE_DUPLICATE_DECLARATION: (
        "Remove or consolidate the redundant equivalent dependency declaration "
        "in the same manifest and declaration context."
    ),
}


def recommendation_for(rule_id: str) -> str:
    return _REMEDIATIONS.get(
        rule_id,
        "Address the dependency declaration hygiene issue using repository-"
        "local evidence only.",
    )
