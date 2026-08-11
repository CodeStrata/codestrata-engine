"""Aggregate extractor — maps controlled sources to identity-free input (Slice 10.5).

Does not traverse repositories, open files, or read report JSON. Callers supply
already-aggregated language labels/counts and rule execution totals.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.repository_aggregate_input import (
    RepositoryAggregateAnalyticsInput,
    build_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
    map_language_label_to_group,
)
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    CommunityRepositoryAggregateAnalyticsPolicy,
    default_repository_aggregate_analytics_policy,
)


def extract_language_mix_from_label_counts(
    label_counts: Mapping[str, int],
    *,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> tuple[LanguageAggregate, ...]:
    """Collapse detector/inventory labels into closed language_group counts.

    Count unit: assessed source files classified into each group.
    Unknown raw labels raise ``invalid_language_group`` (never custom groups).
    """

    active = policy or default_repository_aggregate_analytics_policy()
    totals: Counter[str] = Counter()
    for label, count in label_counts.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_COUNT)
        group = map_language_label_to_group(str(label))
        totals[group] += count
    items = [
        LanguageAggregate(language_group=group, count=count)
        for group, count in totals.items()
    ]
    return build_repository_aggregate_input(
        language_mix=items,
        rule_execution=RuleExecutionAggregate(
            attempted=0, completed=0, skipped=0, failed=0
        ),
        policy=active,
    ).language_mix


def extract_repository_aggregate_input(
    *,
    language_label_counts: Mapping[str, int] | None = None,
    language_mix: Iterable[LanguageAggregate] | None = None,
    attempted: int,
    completed: int,
    skipped: int,
    failed: int,
    rule_execution_by_head: (
        Mapping[str, Mapping[str, int]] | Iterable[RuleExecutionAggregate] | None
    ) = None,
    policy: CommunityRepositoryAggregateAnalyticsPolicy | None = None,
) -> RepositoryAggregateAnalyticsInput:
    """Build a privacy-safe aggregate input from bounded counts only."""

    active = policy or default_repository_aggregate_analytics_policy()
    if language_mix is not None and language_label_counts is not None:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)

    if language_label_counts is not None:
        languages = extract_language_mix_from_label_counts(
            language_label_counts, policy=active
        )
    else:
        languages = tuple(language_mix or ())

    by_head: list[RuleExecutionAggregate] = []
    if rule_execution_by_head is not None:
        if isinstance(rule_execution_by_head, Mapping):
            for head, counts in rule_execution_by_head.items():
                by_head.append(
                    RuleExecutionAggregate(
                        assessment_head=str(head),
                        attempted=int(counts.get("attempted", 0)),
                        completed=int(counts.get("completed", 0)),
                        skipped=int(counts.get("skipped", 0)),
                        failed=int(counts.get("failed", 0)),
                    )
                )
        else:
            by_head.extend(rule_execution_by_head)

    return build_repository_aggregate_input(
        language_mix=languages,
        rule_execution=RuleExecutionAggregate(
            attempted=attempted,
            completed=completed,
            skipped=skipped,
            failed=failed,
        ),
        rule_execution_by_head=by_head,
        policy=active,
    )


__all__ = [
    "extract_language_mix_from_label_counts",
    "extract_repository_aggregate_input",
]
