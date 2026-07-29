"""Read-only context for recommendation providers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.graph.validation import as_tuple
from codestrata.domain.rules import RuleContext


class RecommendationContext(BaseModel):
    """Findings plus graph/inventory context for recommendation derivation.

    Providers must not mutate findings, graphs, or bindings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    rule_context: RuleContext
    findings: tuple[Finding, ...] = ()
    rules_evaluated: tuple[str, ...] = ()
    rules_skipped: tuple[str, ...] = ()

    @field_validator("findings", "rules_evaluated", "rules_skipped", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)

    @classmethod
    def from_rule_evaluation(
        cls,
        *,
        rule_context: RuleContext,
        evaluation: RuleEvaluationResult,
    ) -> RecommendationContext:
        return cls(
            rule_context=rule_context,
            findings=evaluation.findings,
            rules_evaluated=evaluation.rules_evaluated,
            rules_skipped=evaluation.rules_skipped,
        )

    def findings_for_rule(self, rule_id: str) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.rule_id == rule_id)
