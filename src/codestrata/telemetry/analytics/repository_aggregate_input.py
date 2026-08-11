"""Identity-free repository aggregate analytics input (Epic 10 Slice 10.5).

Contains only bounded language-group counts and rule execution aggregates.
Never carries repository objects, files, rules, Findings, or paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
    normalize_language_aggregates,
    normalize_rule_execution_aggregate,
    normalize_rule_execution_by_head,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)


@dataclass(frozen=True, slots=True)
class RepositoryAggregateAnalyticsInput:
    """Privacy-safe aggregate source for repository aggregate analytics."""

    language_mix: tuple[LanguageAggregate, ...]
    rule_execution: RuleExecutionAggregate
    rule_execution_by_head: tuple[RuleExecutionAggregate, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "language_mix": [item.to_stable_dict() for item in self.language_mix],
            "rule_execution": self.rule_execution.to_stable_dict(),
            "rule_execution_by_head": [
                item.to_stable_dict() for item in self.rule_execution_by_head
            ],
        }


def build_repository_aggregate_input(
    *,
    language_mix: tuple[LanguageAggregate, ...] | list[LanguageAggregate],
    rule_execution: RuleExecutionAggregate,
    rule_execution_by_head: (
        tuple[RuleExecutionAggregate, ...] | list[RuleExecutionAggregate] | None
    ) = None,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsInput:
    active = policy or default_repository_aggregate_analytics_policy()
    active.validate()
    languages = normalize_language_aggregates(
        language_mix,
        max_count=active.max_language_file_count,
        max_groups=active.max_language_groups,
        omit_zero=active.omit_zero_language_counts,
    )
    overall = normalize_rule_execution_aggregate(
        rule_execution, max_count=active.max_rule_execution_count
    )
    if overall.assessment_head is not None:
        # Overall totals must not carry a head — use by_head for grouping.
        from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode

        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    by_head = normalize_rule_execution_by_head(
        rule_execution_by_head or (),
        max_count=active.max_rule_execution_count,
        max_groups=active.max_head_rule_groups,
    )
    return RepositoryAggregateAnalyticsInput(
        language_mix=languages,
        rule_execution=overall,
        rule_execution_by_head=by_head,
    )


__all__ = [
    "RepositoryAggregateAnalyticsInput",
    "build_repository_aggregate_input",
]
