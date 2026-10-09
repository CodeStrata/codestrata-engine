"""Launch-ratified composition budgets (E01.1 / E04.1)."""

from __future__ import annotations

from codestrata.domain.contracts.catalog import load_launch_ratification

FLOATING_REF_MARKERS = frozenset(
    {"latest", "*", "main", "head", "floating", "next", "default"}
)


def composition_budgets() -> tuple[int, int, int, int]:
    budgets = load_launch_ratification().budgets
    return (
        budgets.ruleset_parent_depth,
        budgets.max_effective_rules,
        budgets.yaml_document_bytes,
        budgets.yaml_max_nesting,
    )
