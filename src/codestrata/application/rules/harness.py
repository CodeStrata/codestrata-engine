"""Reusable testing harness for Shared Rule Platform authors."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.analysis_service import RuleAnalysisService
from codestrata.application.rules.context_factory import RuleExecutionContextFactory
from codestrata.application.rules.executor import RuleExecutor
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.models import RulePlatformExecutionResult
from codestrata.application.rules.planner import RulePlanner
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.suppression_service import RuleSuppressionService
from codestrata.domain.findings.models import Finding
from codestrata.domain.rules.applicability import RuleSuppression
from codestrata.domain.rules.context import RuleExecutionContext, RuleExecutionPolicy
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleResultStatus
from codestrata.domain.rules.results import RuleMatch


class RuleTestHarness:
    """Minimal boilerplate for exercising one or more SharedRules."""

    def __init__(
        self,
        rules: Sequence[SharedRule] = (),
        *,
        suppressions: tuple[RuleSuppression, ...] = (),
        policy: RuleExecutionPolicy | None = None,
    ) -> None:
        self.registry = RuleRegistry()
        if rules:
            self.registry.register_collection(rules, production=False)
        self.policy = policy or RuleExecutionPolicy()
        self.context_factory = RuleExecutionContextFactory()
        self.service = RuleAnalysisService(
            registry=self.registry,
            planner=RulePlanner(),
            executor=RuleExecutor(suppression_service=RuleSuppressionService(suppressions)),
            finding_mapper=RuleFindingMapper(),
            suppressions=suppressions,
        )

    def build_context(self, **kwargs: object) -> RuleExecutionContext:
        kwargs.setdefault("repository_id", "repo:test")
        kwargs.setdefault("policy", self.policy)
        return self.context_factory.build(**kwargs)  # type: ignore[arg-type]

    def execute_one(
        self,
        rule: SharedRule,
        context: RuleExecutionContext | None = None,
    ) -> RulePlatformExecutionResult:
        rule_id = str(rule.metadata.rule_id)
        known = {
            str(view.metadata.rule_id)
            for view in self.registry.list_rules(include_non_production=True)
        }
        if rule_id not in known:
            self.registry.register(rule, production=False)
        ctx = context or self.build_context()
        return self.service.execute_rules(
            ctx,
            include_rule_ids=(rule_id,),
            include_non_production=True,
        )

    def assert_status(
        self,
        rule_id: str,
        result: RulePlatformExecutionResult,
        status: RuleResultStatus,
    ) -> None:
        record = next(item for item in result.records if item.rule_id == rule_id)
        assert record.status is status, f"expected {status}, got {record.status}"

    def assert_match_count(self, result: RulePlatformExecutionResult, expected: int) -> None:
        assert len(result.matches) == expected

    def assert_evidence_present(self, match: RuleMatch, *, subject: str) -> None:
        assert any(item.subject_reference == subject for item in match.evidence)

    def map_findings(self, result: RulePlatformExecutionResult) -> tuple[Finding, ...]:
        return self.service.map_findings(result)
