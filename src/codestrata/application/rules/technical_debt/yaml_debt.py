"""YAML-bound retained technical_debt.* rules (E08.3).

Catalog metadata is YAML. Native evaluation reuses the existing complexity
operators and does not re-parse source.
"""

from __future__ import annotations

from typing import Any, cast

from codestrata.application.rules.technical_debt.rules import (
    DeepNestingRule,
    ExcessiveBranchingRule,
    ExcessiveParametersRule,
    LargeCallableRule,
    OversizedTypeRule,
)
from codestrata.application.rules.technical_debt.yaml_catalog import bundled_quality_rule
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
from codestrata.domain.technical_debt.ids import PACK_ID


class _YamlRetainedDebtRule:
    def __init__(self, rule_id: str, native: Any) -> None:
        catalog = bundled_quality_rule(rule_id)
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
            category=RuleCategory.TECHNICAL_DEBT,
            default_severity=self._severity,
            confidence=native_meta.confidence,
            supported_languages=tuple(str(item) for item in languages),
            tags=("technical_debt", PACK_ID, "yaml", "retained"),
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


class YamlLargeCallableRule(_YamlRetainedDebtRule):
    def __init__(self, max_physical_lines: int = 50) -> None:
        super().__init__(
            "technical_debt.large-callable",
            LargeCallableRule(max_physical_lines=max_physical_lines),
        )


class YamlExcessiveBranchingRule(_YamlRetainedDebtRule):
    def __init__(self, max_branch_points: int = 10) -> None:
        super().__init__(
            "technical_debt.excessive-branching",
            ExcessiveBranchingRule(max_branch_points=max_branch_points),
        )


class YamlDeepNestingRule(_YamlRetainedDebtRule):
    def __init__(self, max_nesting_depth: int = 4) -> None:
        super().__init__(
            "technical_debt.deep-nesting",
            DeepNestingRule(max_nesting_depth=max_nesting_depth),
        )


class YamlExcessiveParametersRule(_YamlRetainedDebtRule):
    def __init__(self, max_parameters: int = 5) -> None:
        super().__init__(
            "technical_debt.excessive-parameters",
            ExcessiveParametersRule(max_parameters=max_parameters),
        )


class YamlOversizedTypeRule(_YamlRetainedDebtRule):
    def __init__(self, max_physical_lines: int = 300) -> None:
        super().__init__(
            "technical_debt.oversized-type",
            OversizedTypeRule(max_physical_lines=max_physical_lines),
        )


__all__ = [
    "YamlDeepNestingRule",
    "YamlExcessiveBranchingRule",
    "YamlExcessiveParametersRule",
    "YamlLargeCallableRule",
    "YamlOversizedTypeRule",
]
