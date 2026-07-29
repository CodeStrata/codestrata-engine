"""Transport-neutral Shared Rule Platform orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.context_factory import RuleExecutionContextFactory
from codestrata.application.rules.executor import RuleExecutor
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.inspection_service import RuleInspectionService
from codestrata.application.rules.models import (
    RuleExecutionPlan,
    RuleExplanation,
    RuleInspectionView,
    RulePlatformExecutionResult,
)
from codestrata.application.rules.planner import RulePlanner
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.suppression_service import RuleSuppressionService
from codestrata.domain.findings.models import Finding
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleCategory


class RuleAnalysisService:
    """Orchestrates registry, planning, execution, mapping, and explanation."""

    def __init__(
        self,
        *,
        registry: RuleRegistry,
        planner: RulePlanner | None = None,
        executor: RuleExecutor | None = None,
        context_factory: RuleExecutionContextFactory | None = None,
        finding_mapper: RuleFindingMapper | None = None,
        inspection: RuleInspectionService | None = None,
        suppressions: tuple[RuleSuppression, ...] = (),
    ) -> None:
        self._registry = registry
        self._planner = planner or RulePlanner()
        self._suppressions = RuleSuppressionService(suppressions)
        self._executor = executor or RuleExecutor(suppression_service=self._suppressions)
        self._context_factory = context_factory or RuleExecutionContextFactory()
        self._finding_mapper = finding_mapper or RuleFindingMapper()
        self._inspection = inspection or RuleInspectionService(registry)

    @property
    def registry(self) -> RuleRegistry:
        return self._registry

    def list_rules(
        self,
        *,
        category: RuleCategory | None = None,
        language: str | None = None,
        include_non_production: bool = False,
    ) -> tuple[RuleInspectionView, ...]:
        return self._registry.list_rules(
            category=category,
            language=language,
            include_non_production=include_non_production,
        )

    def inspect_rule(self, rule_id: str) -> RuleInspectionView:
        rule = self._registry.get(rule_id)
        return RuleInspectionView(
            metadata=rule.metadata,
            production=self._registry.is_production(str(rule.metadata.rule_id)),
        )

    def plan_rules(
        self,
        context: RuleExecutionContext,
        *,
        enabled_categories: Sequence[RuleCategory] | None = None,
        include_rule_ids: Sequence[str] | None = None,
        exclude_rule_ids: Sequence[str] | None = None,
        include_non_production: bool = False,
    ) -> RuleExecutionPlan:
        return self._planner.plan(
            self._registry,
            context,
            enabled_categories=enabled_categories,
            include_rule_ids=include_rule_ids,
            exclude_rule_ids=exclude_rule_ids,
            include_non_production=include_non_production,
        )

    def execute_rules(
        self,
        context: RuleExecutionContext,
        *,
        enabled_categories: Sequence[RuleCategory] | None = None,
        include_rule_ids: Sequence[str] | None = None,
        exclude_rule_ids: Sequence[str] | None = None,
        include_non_production: bool = False,
    ) -> RulePlatformExecutionResult:
        plan = self.plan_rules(
            context,
            enabled_categories=enabled_categories,
            include_rule_ids=include_rule_ids,
            exclude_rule_ids=exclude_rule_ids,
            include_non_production=include_non_production,
        )
        return self._executor.execute(self._registry, plan, context)

    def map_findings(self, result: RulePlatformExecutionResult) -> tuple[Finding, ...]:
        category_by_rule = {
            record.rule_id: record.category or RuleCategory.PLATFORM for record in result.records
        }
        return self._finding_mapper.map_matches(
            result.matches,
            category_by_rule=category_by_rule,
        )

    def explain_rule_plan(self, plan: RuleExecutionPlan) -> tuple[RuleExplanation, ...]:
        return self._inspection.explain_plan(plan)

    def explain_rule_result(
        self,
        result: RulePlatformExecutionResult,
    ) -> tuple[RuleExplanation, ...]:
        return self._inspection.explain_result(result)

    def explain_rule_metadata(self, rule_id: str) -> RuleExplanation:
        return self._inspection.explain_metadata(rule_id)

    def create_context(self, **kwargs: object) -> RuleExecutionContext:
        return self._context_factory.build(**kwargs)  # type: ignore[arg-type]
