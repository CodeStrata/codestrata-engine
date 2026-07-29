"""Concise factual remediation text for Technical Debt complexity rules."""

from __future__ import annotations

from codestrata.domain.technical_debt.ids import (
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_EXCESSIVE_PARAMETERS,
    RULE_LARGE_CALLABLE,
    RULE_OVERSIZED_TYPE,
)

_REMEDIATIONS: dict[str, str] = {
    RULE_LARGE_CALLABLE: (
        "Split the callable into smaller units with single responsibilities so "
        "physical line count falls at or below the configured threshold."
    ),
    RULE_EXCESSIVE_BRANCHING: (
        "Reduce conditional and loop branching (extract helpers, use early returns, "
        "or replace nested branches) so branch-point count falls at or below the "
        "configured threshold."
    ),
    RULE_DEEP_NESTING: (
        "Flatten control-flow nesting (guard clauses, helper extraction) so maximum "
        "nesting depth falls at or below the configured threshold."
    ),
    RULE_EXCESSIVE_PARAMETERS: (
        "Reduce the formal parameter list (introduce a parameter object or split "
        "the callable) so parameter count falls at or below the configured threshold."
    ),
    RULE_OVERSIZED_TYPE: (
        "Split or extract members from the type/module so its physical size falls "
        "at or below the configured threshold."
    ),
}


def recommendation_for(rule_id: str) -> str:
    return _REMEDIATIONS.get(rule_id, "Reduce structural complexity using evidence-backed edits.")
