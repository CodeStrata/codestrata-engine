"""Incremental rule execution with conservative reuse."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from codestrata.application.incremental.errors import IncrementalRuleExecutionError
from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.rule_engine import RuleEngine


class IncrementalRuleScopeProvider(Protocol):
    def supports_selective_execution(self) -> bool: ...

    def globally_affected_rules(self) -> frozenset[str]: ...


class DefaultRuleScopeProvider:
    """Builtin rules do not expose a complete selective scope contract."""

    def supports_selective_execution(self) -> bool:
        return False

    def globally_affected_rules(self) -> frozenset[str]:
        return frozenset()


class IncrementalRuleExecutor:
    """Rerun rules against a merged assessment package; reuse only when safe."""

    def __init__(
        self,
        *,
        rule_engine: RuleEngine | None = None,
        scope_provider: IncrementalRuleScopeProvider | None = None,
        allow_reuse: bool = True,
    ) -> None:
        self._engine = rule_engine or RuleEngine()
        self._scope = scope_provider or DefaultRuleScopeProvider()
        self._allow_reuse = allow_reuse

    def execute(
        self,
        pipeline_result: GraphAssessmentPipelineResult,
        *,
        previous_findings: Sequence[Finding] = (),
        impacted_subject_ids: frozenset[str] = frozenset(),
    ) -> tuple[RuleEvaluationResult, int, int]:
        """Return (evaluation, reused_count, recomputed_count)."""

        # Phase 2F.2: selective scope is incomplete for builtin rules → full rerun.
        if not self._scope.supports_selective_execution():
            evaluation = self._engine.evaluate_pipeline_result(pipeline_result)
            return evaluation, 0, len(evaluation.findings)

        # Reserved path for future selective catalogs.
        evaluation = self._engine.evaluate_pipeline_result(pipeline_result)
        if not self._allow_reuse:
            return evaluation, 0, len(evaluation.findings)

        reused: list[Finding] = []
        for finding in previous_findings:
            if _looks_like_uuid(finding.id):
                continue
            subjects = {str(node_id) for node_id in finding.affected_assessment_node_ids}
            if subjects & set(impacted_subject_ids):
                continue
            reused.append(finding)

        by_id = {finding.id: finding for finding in evaluation.findings}
        for finding in reused:
            by_id.setdefault(finding.id, finding)
        merged = tuple(by_id[key] for key in sorted(by_id))
        if len(merged) != len(by_id):
            raise IncrementalRuleExecutionError(
                "Duplicate finding identities after merge",
                reason_code="duplicate_finding_id",
                failed_step="rule_execution",
            )
        result = RuleEvaluationResult.from_findings(
            findings=merged,
            rules_evaluated=evaluation.rules_evaluated,
            rules_skipped=evaluation.rules_skipped,
        )
        return result, len(reused), max(0, len(evaluation.findings))


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value.strip())
    except ValueError:
        return False
    return True
