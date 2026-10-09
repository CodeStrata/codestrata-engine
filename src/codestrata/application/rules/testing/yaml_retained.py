"""YAML-bound retained testing.test-00N rules (E08.3).

Catalog metadata is YAML. Native evaluation reuses repository-testing operators.
"""

from __future__ import annotations

from typing import Any, cast

from codestrata.application.rules.testing.rules import (
    CoverageWithoutCiInvocationRule,
    DeclaredWithoutObservationRule,
    DisabledOrSkippedMarkersRule,
    UnconfirmedCandidatesRule,
)
from codestrata.application.rules.testing.yaml_catalog import bundled_testing_rule
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import SharedRuleEvaluationResult
from codestrata.domain.testing.ids import PACK_ID


class _YamlRetainedTestingRule:
    __test__ = False

    def __init__(self, rule_id: str, native: Any) -> None:
        catalog = bundled_testing_rule(rule_id)
        self._catalog = catalog
        self._rule_id = str(catalog["rule_id"])
        self._native = native
        severity = catalog["default_severity"]
        if isinstance(severity, RuleSeverity):
            self._severity = severity
        else:
            self._severity = RuleSeverity(str(severity))

    @property
    def metadata(self) -> RuleMetadata:
        native_meta = self._native.metadata
        languages = self._catalog.get("languages") or native_meta.supported_languages
        return RuleMetadata(
            rule_id=RuleId(self._rule_id),
            version=RuleVersion.parse(str(self._catalog.get("version") or "1.0.0")),
            title=str(self._catalog["title"]),
            description=str(self._catalog["description"]),
            category=RuleCategory.TESTING,
            default_severity=self._severity,
            confidence=native_meta.confidence,
            supported_languages=tuple(str(item) for item in languages),
            tags=("testing", PACK_ID, "yaml", "retained"),
            remediation_summary=native_meta.remediation_summary,
            documentation_reference=str(self._catalog.get("documentation_url") or ""),
            enabled_by_default=True,
            experimental=False,
            requires_enterprise_context=False,
            incremental_behaviors=(
                RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
                RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return cast(RuleApplicability, self._native.evaluate_applicability(context))

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        return cast(SharedRuleEvaluationResult, self._native.evaluate(context))


class YamlDisabledOrSkippedRule(_YamlRetainedTestingRule):
    def __init__(self) -> None:
        super().__init__("testing.test-001", DisabledOrSkippedMarkersRule())


class YamlUnconfirmedCandidatesRule(_YamlRetainedTestingRule):
    def __init__(self) -> None:
        super().__init__("testing.test-002", UnconfirmedCandidatesRule())


class YamlDeclaredWithoutObservationRule(_YamlRetainedTestingRule):
    def __init__(self) -> None:
        super().__init__("testing.test-003", DeclaredWithoutObservationRule())


class YamlCoverageWithoutCiRule(_YamlRetainedTestingRule):
    def __init__(self) -> None:
        super().__init__("testing.test-005", CoverageWithoutCiInvocationRule())


__all__ = [
    "YamlCoverageWithoutCiRule",
    "YamlDeclaredWithoutObservationRule",
    "YamlDisabledOrSkippedRule",
    "YamlUnconfirmedCandidatesRule",
]
