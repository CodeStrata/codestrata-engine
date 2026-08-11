"""Repository aggregate language mix and rule count tests (Slice 10.5)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.repository_aggregate_extractor import (
    extract_language_mix_from_label_counts,
    extract_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
    map_language_label_to_group,
    normalize_language_aggregates,
    normalize_rule_execution_aggregate,
)


def test_language_label_mapping() -> None:
    assert map_language_label_to_group("TypeScript") == "javascript_typescript"
    assert map_language_label_to_group("C#") == "csharp_dotnet"
    assert map_language_label_to_group("python") == "python"
    with pytest.raises(AnalyticsError) as exc:
        map_language_label_to_group("Kotlin")
    assert exc.value.code is AnalyticsErrorCode.INVALID_LANGUAGE_GROUP


def test_zero_counts_omitted() -> None:
    rows = normalize_language_aggregates(
        [
            LanguageAggregate("python", 3),
            LanguageAggregate("java", 0),
        ]
    )
    assert rows == (LanguageAggregate("python", 3),)


def test_duplicate_language_rejected() -> None:
    with pytest.raises(AnalyticsError) as exc:
        normalize_language_aggregates(
            [
                LanguageAggregate("python", 1),
                LanguageAggregate("python", 2),
            ]
        )
    assert exc.value.code is AnalyticsErrorCode.DUPLICATE_LANGUAGE_GROUP


def test_language_count_cap() -> None:
    with pytest.raises(AnalyticsError) as exc:
        normalize_language_aggregates([LanguageAggregate("python", 10_001)])
    assert exc.value.code is AnalyticsErrorCode.LANGUAGE_COUNT_EXCEEDED


def test_extractor_merges_js_ts() -> None:
    mix = extract_language_mix_from_label_counts(
        {"JavaScript": 2, "TypeScript": 3, "Python": 1}
    )
    assert mix == (
        LanguageAggregate("javascript_typescript", 5),
        LanguageAggregate("python", 1),
    )


def test_rule_semantics_consistency() -> None:
    ok = normalize_rule_execution_aggregate(
        RuleExecutionAggregate(attempted=10, completed=7, skipped=2, failed=1)
    )
    assert ok.completed == 7
    with pytest.raises(AnalyticsError) as exc:
        normalize_rule_execution_aggregate(
            RuleExecutionAggregate(attempted=5, completed=6, skipped=0, failed=0)
        )
    assert exc.value.code is AnalyticsErrorCode.INCONSISTENT_RULE_COUNTS


def test_extract_full_input() -> None:
    payload = extract_repository_aggregate_input(
        language_label_counts={"java": 4, "php": 1},
        attempted=20,
        completed=18,
        skipped=1,
        failed=1,
        rule_execution_by_head={
            "security_intelligence": {
                "attempted": 8,
                "completed": 7,
                "skipped": 1,
                "failed": 0,
            }
        },
    )
    assert payload.language_mix[0].language_group == "java"
    assert payload.rule_execution.attempted == 20
    assert payload.rule_execution_by_head[0].assessment_head == "security_intelligence"
