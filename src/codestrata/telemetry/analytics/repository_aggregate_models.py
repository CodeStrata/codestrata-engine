"""Repository aggregate analytics typed models (Epic 10 Slice 10.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import _APPROVED_ASSESSMENT_HEADS
from codestrata.telemetry.analytics.repository_aggregate_policy import (
    DEFAULT_MAX_LANGUAGE_FILE_COUNT,
    DEFAULT_MAX_RULE_EXECUTION_COUNT,
)

# Authoritative closed vocabulary mapped from evidence language tokens.
APPROVED_LANGUAGE_GROUPS: frozenset[str] = frozenset(
    {
        "python",
        "java",
        "javascript_typescript",
        "php",
        "csharp_dotnet",
        "unclassified",
    }
)

# Map common detector / inventory labels → analytics language_group.
_LANGUAGE_LABEL_ALIASES: dict[str, str] = {
    "python": "python",
    "java": "java",
    "javascript": "javascript_typescript",
    "typescript": "javascript_typescript",
    "js": "javascript_typescript",
    "ts": "javascript_typescript",
    "php": "php",
    "csharp": "csharp_dotnet",
    "c#": "csharp_dotnet",
    "c#/.net": "csharp_dotnet",
    "unclassified": "unclassified",
    "unknown": "unclassified",
    "other": "unclassified",
}


@dataclass(frozen=True, slots=True)
class LanguageAggregate:
    """Count of assessed source files classified into a language group."""

    language_group: str
    count: int

    def to_stable_dict(self) -> dict[str, Any]:
        return {"count": self.count, "language_group": self.language_group}


@dataclass(frozen=True, slots=True)
class RuleExecutionAggregate:
    """Bounded rule execution totals (no rule IDs/names).

    Semantics:
    - attempted: rules selected/planned for execution
    - completed: rules that finished evaluation (including zero Findings)
    - skipped: rules not executed (disabled, not selected, not applicable, …)
    - failed: rules that raised an internal evaluation failure

    completed is NOT “Finding produced”.
    zero Findings is NOT repository health.
    failed is NOT assessment command failure.
    """

    attempted: int
    completed: int
    skipped: int
    failed: int
    assessment_head: str | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "attempted": self.attempted,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
        }
        if self.assessment_head is not None:
            payload["assessment_head"] = self.assessment_head
        return {key: payload[key] for key in sorted(payload)}


def map_language_label_to_group(label: str) -> str:
    """Map a known detector/inventory label to a closed language_group.

    Unknown raw strings raise — they are never emitted as custom groups.
    """

    key = label.strip().lower()
    if key in APPROVED_LANGUAGE_GROUPS:
        return key
    mapped = _LANGUAGE_LABEL_ALIASES.get(key)
    if mapped is None:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_GROUP)
    return mapped


def assert_non_negative_bounded_count(
    value: int,
    *,
    maximum: int,
    exceeded_code: AnalyticsErrorCode = AnalyticsErrorCode.INVALID_LANGUAGE_COUNT,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_COUNT)
    if value < 0:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_COUNT)
    if value > maximum:
        raise AnalyticsError(exceeded_code)
    return value


def normalize_language_aggregates(
    items: tuple[LanguageAggregate, ...] | list[LanguageAggregate],
    *,
    max_count: int = DEFAULT_MAX_LANGUAGE_FILE_COUNT,
    max_groups: int = 6,
    omit_zero: bool = True,
) -> tuple[LanguageAggregate, ...]:
    if len(items) > max_groups:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    seen: set[str] = set()
    normalized: list[LanguageAggregate] = []
    for item in items:
        group = item.language_group
        if group not in APPROVED_LANGUAGE_GROUPS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_GROUP)
        if group in seen:
            raise AnalyticsError(AnalyticsErrorCode.DUPLICATE_LANGUAGE_GROUP)
        seen.add(group)
        count = assert_non_negative_bounded_count(
            item.count,
            maximum=max_count,
            exceeded_code=AnalyticsErrorCode.LANGUAGE_COUNT_EXCEEDED,
        )
        if omit_zero and count == 0:
            continue
        normalized.append(LanguageAggregate(language_group=group, count=count))
    return tuple(sorted(normalized, key=lambda row: row.language_group))


def normalize_rule_execution_aggregate(
    aggregate: RuleExecutionAggregate,
    *,
    max_count: int = DEFAULT_MAX_RULE_EXECUTION_COUNT,
) -> RuleExecutionAggregate:
    attempted = assert_non_negative_bounded_count(
        aggregate.attempted,
        maximum=max_count,
        exceeded_code=AnalyticsErrorCode.INVALID_RULE_COUNT,
    )
    completed = assert_non_negative_bounded_count(
        aggregate.completed,
        maximum=max_count,
        exceeded_code=AnalyticsErrorCode.INVALID_RULE_COUNT,
    )
    skipped = assert_non_negative_bounded_count(
        aggregate.skipped,
        maximum=max_count,
        exceeded_code=AnalyticsErrorCode.INVALID_RULE_COUNT,
    )
    failed = assert_non_negative_bounded_count(
        aggregate.failed,
        maximum=max_count,
        exceeded_code=AnalyticsErrorCode.INVALID_RULE_COUNT,
    )
    # Soft consistency: completed + skipped + failed should not exceed attempted
    # when all three partitions are disjoint. Product may under-count partitions;
    # require only completed <= attempted and failed <= attempted.
    if completed > attempted or failed > attempted or skipped > attempted:
        raise AnalyticsError(AnalyticsErrorCode.INCONSISTENT_RULE_COUNTS)
    head = aggregate.assessment_head
    if head is not None:
        if head not in _APPROVED_ASSESSMENT_HEADS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
    return RuleExecutionAggregate(
        attempted=attempted,
        completed=completed,
        skipped=skipped,
        failed=failed,
        assessment_head=head,
    )


def normalize_rule_execution_by_head(
    items: tuple[RuleExecutionAggregate, ...] | list[RuleExecutionAggregate],
    *,
    max_count: int = DEFAULT_MAX_RULE_EXECUTION_COUNT,
    max_groups: int = 9,
) -> tuple[RuleExecutionAggregate, ...]:
    if len(items) > max_groups:
        raise AnalyticsError(AnalyticsErrorCode.TOO_MANY_HEADS)
    seen: set[str] = set()
    normalized: list[RuleExecutionAggregate] = []
    for item in items:
        if item.assessment_head is None:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
        if item.assessment_head in seen:
            raise AnalyticsError(AnalyticsErrorCode.DUPLICATE_HEAD)
        seen.add(item.assessment_head)
        normalized.append(
            normalize_rule_execution_aggregate(item, max_count=max_count)
        )
    return tuple(sorted(normalized, key=lambda row: row.assessment_head or ""))


__all__ = [
    "APPROVED_LANGUAGE_GROUPS",
    "LanguageAggregate",
    "RuleExecutionAggregate",
    "assert_non_negative_bounded_count",
    "map_language_label_to_group",
    "normalize_language_aggregates",
    "normalize_rule_execution_aggregate",
    "normalize_rule_execution_by_head",
]
