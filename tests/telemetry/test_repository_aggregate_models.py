"""Repository aggregate models/validation/compatibility/extractor stubs (10.5)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.analytics.errors import AnalyticsError
from codestrata.telemetry.analytics.repository_aggregate_compatibility import (
    compatible_repository_aggregate_schema_versions,
    migrate_repository_aggregate_mapping,
)
from codestrata.telemetry.analytics.repository_aggregate_models import (
    LanguageAggregate,
    RuleExecutionAggregate,
)
from codestrata.telemetry.analytics.repository_aggregate_input import (
    build_repository_aggregate_input,
)


def test_models_stable_dict() -> None:
    lang = LanguageAggregate("php", 4).to_stable_dict()
    assert lang == {"count": 4, "language_group": "php"}
    rule = RuleExecutionAggregate(3, 2, 1, 0).to_stable_dict()
    assert set(rule) == {"attempted", "completed", "failed", "skipped"}


def test_overall_must_not_carry_head() -> None:
    with pytest.raises(AnalyticsError):
        build_repository_aggregate_input(
            language_mix=[LanguageAggregate("python", 1)],
            rule_execution=RuleExecutionAggregate(
                attempted=1,
                completed=1,
                skipped=0,
                failed=0,
                assessment_head="security_intelligence",
            ),
        )


def test_compatibility_matrix() -> None:
    assert compatible_repository_aggregate_schema_versions() == frozenset({"1.0"})
    assert migrate_repository_aggregate_mapping({"schema_version": "1.0"}) == {
        "schema_version": "1.0"
    }
