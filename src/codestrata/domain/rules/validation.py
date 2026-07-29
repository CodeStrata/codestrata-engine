"""Validation helpers for Shared Rule Platform results."""

from __future__ import annotations

from codestrata.domain.rules.context import RuleExecutionPolicy
from codestrata.domain.rules.errors import RuleResultValidationError
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult


def validate_matches_against_policy(
    matches: tuple[RuleMatch, ...],
    *,
    policy: RuleExecutionPolicy,
    rule_id: str,
) -> tuple[RuleMatch, ...]:
    if len(matches) > policy.max_matches_per_rule:
        raise RuleResultValidationError(
            f"rule {rule_id} exceeded max_matches_per_rule ({policy.max_matches_per_rule})",
            reason_code="max_matches_per_rule",
            rule_id=rule_id,
        )
    for match in matches:
        if len(match.evidence) > policy.max_evidence_per_match:
            raise RuleResultValidationError(
                f"rule {rule_id} exceeded max_evidence_per_match",
                reason_code="max_evidence_per_match",
                rule_id=rule_id,
            )
    return matches


def validate_evaluation_result(
    result: SharedRuleEvaluationResult,
    *,
    policy: RuleExecutionPolicy,
    rule_id: str,
) -> SharedRuleEvaluationResult:
    validate_matches_against_policy(result.matches, policy=policy, rule_id=rule_id)
    return result
