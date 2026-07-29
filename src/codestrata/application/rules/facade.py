"""Unified rule execution facade (Phase 4.1.1).

Assessment continues to use :class:`~codestrata.services.rule_engine.engine.RuleEngine`
directly. This facade is the strategic entry point for future packs and for
compatibility evaluation of legacy rules through adapters.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.executor import RuleExecutor
from codestrata.application.rules.legacy_adapter import LegacyRuleAdapter, adapt_legacy_rules
from codestrata.application.rules.models import RuleExecutionPlan, RulePlatformExecutionResult
from codestrata.application.rules.planner import RulePlanner
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.suppression_service import RuleSuppressionService
from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
    RuleExecutionPolicy,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.models import Rule, RuleContext
from codestrata.services.rule_engine.engine import RuleEngine
from codestrata.services.rule_engine.rules.builtin import builtin_rules


class RuleExecutionFacade:
    """Choose and orchestrate legacy vs shared rule execution paths.

    - :meth:`evaluate` — identical to :class:`RuleEngine` (assessment-compatible)
    - :meth:`evaluate_adapted` — legacy rules via :class:`LegacyRuleAdapter`
      with Finding passthrough (compatibility / migration verification)
    - :meth:`execute_shared` — native Shared Rule Platform execution
    """

    def __init__(
        self,
        *,
        legacy_engine: RuleEngine | None = None,
        shared_registry: RuleRegistry | None = None,
        planner: RulePlanner | None = None,
        executor: RuleExecutor | None = None,
    ) -> None:
        self._legacy_engine = legacy_engine or RuleEngine()
        self._shared_registry = shared_registry or RuleRegistry()
        self._planner = planner or RulePlanner()
        self._executor = executor or RuleExecutor(suppression_service=RuleSuppressionService())

    @property
    def legacy_engine(self) -> RuleEngine:
        return self._legacy_engine

    @property
    def shared_registry(self) -> RuleRegistry:
        return self._shared_registry

    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        """Primary Assessment Graph path — delegates to RuleEngine unchanged."""

        return self._legacy_engine.evaluate(context)

    def evaluate_adapted(
        self,
        context: RuleContext,
        *,
        rules: Sequence[Rule] | None = None,
    ) -> RuleEvaluationResult:
        """Execute legacy rules through adapters; preserve Finding objects.

        Uses the same applicability and aggregation algorithm as RuleEngine so
        findings are semantically identical for the same inputs.
        """

        loaded: tuple[Rule, ...]
        if rules is not None:
            loaded = tuple(sorted(rules, key=lambda rule: rule.id()))
        else:
            loaded = self._legacy_engine.rules

        findings: list[Finding] = []
        evaluated: list[str] = []
        skipped: list[str] = []
        seen_ids: set[str] = set()

        for rule in loaded:
            adapter = LegacyRuleAdapter(rule)
            if not adapter.is_applicable_legacy(context):
                skipped.append(rule.id())
                continue
            result = adapter.evaluate_legacy(context)
            evaluated.append(rule.id())
            if result.skipped:
                skipped.append(rule.id())
            for finding in result.findings:
                if finding.id in seen_ids:
                    continue
                seen_ids.add(finding.id)
                findings.append(finding)

        return RuleEvaluationResult.from_findings(
            findings=tuple(findings),
            rules_evaluated=tuple(evaluated),
            rules_skipped=tuple(skipped),
        )

    def register_shared_rules(
        self,
        rules: Sequence[SharedRule],
        *,
        production: bool = True,
    ) -> None:
        self._shared_registry.register_collection(rules, production=production)

    def register_legacy_as_shared(
        self,
        rules: Sequence[Rule] | None = None,
        *,
        production: bool = False,
    ) -> tuple[LegacyRuleAdapter, ...]:
        """Register adapted legacy rules on the shared registry (opt-in)."""

        adapters = adapt_legacy_rules(tuple(rules) if rules is not None else builtin_rules())
        self._shared_registry.register_collection(adapters, production=production)
        return adapters

    def execute_shared(
        self,
        context: RuleExecutionContext,
        *,
        include_rule_ids: Sequence[str] | None = None,
        include_non_production: bool = False,
    ) -> RulePlatformExecutionResult:
        """Execute SharedRules (native or adapted) through the platform executor."""

        plan = self._planner.plan(
            self._shared_registry,
            context,
            include_rule_ids=include_rule_ids,
            include_non_production=include_non_production,
        )
        return self._executor.execute(self._shared_registry, plan, context)

    def plan_shared(
        self,
        context: RuleExecutionContext,
        *,
        include_non_production: bool = False,
    ) -> RuleExecutionPlan:
        return self._planner.plan(
            self._shared_registry,
            context,
            include_non_production=include_non_production,
        )


def rule_execution_context_from_legacy(
    context: RuleContext,
    *,
    policy: RuleExecutionPolicy | None = None,
) -> RuleExecutionContext:
    """Build a Shared Rule Platform context that carries the legacy RuleContext."""

    languages = {key.lower() for key in context.bound_keys()}
    for entry in context.manifest.files:
        if entry.language:
            languages.add(entry.language.strip().lower())
    return RuleExecutionContext(
        repository=RepositoryFactView(
            repository_id=context.manifest.identity.repository_key,
            repository_type=None,
            display_name=None,
            basenames=tuple(sorted(context.basenames())),
            relative_paths=tuple(sorted(context.relative_paths())),
        ),
        languages=LanguageInventoryView(languages=tuple(sorted(languages))),
        assessment_graph=context.assessment_graph,
        repository_graph=context.repository_graph,
        engineering_knowledge_graph=context.knowledge_graph,
        legacy_rule_context=context,
        policy=policy or RuleExecutionPolicy(),
        provenance={"source": "legacy_rule_context"},
    )
