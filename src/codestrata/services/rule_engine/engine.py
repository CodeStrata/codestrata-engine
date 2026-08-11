"""Deterministic Assessment Graph Rule Engine."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.rules import Rule, RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.rule_engine.rules.builtin import builtin_rules


class RuleEngine:
    """Load and execute deterministic Assessment Graph rules."""

    def __init__(self, rules: Sequence[Rule] | None = None) -> None:
        loaded: tuple[Rule, ...] = tuple(rules) if rules is not None else builtin_rules()
        # Stable order by rule id for deterministic aggregation.
        self._rules: tuple[Rule, ...] = tuple(sorted(loaded, key=lambda rule: rule.id()))

    @property
    def rules(self) -> tuple[Rule, ...]:
        return self._rules

    def evaluate(self, context: RuleContext) -> RuleEvaluationResult:
        """Evaluate all applicable rules without mutating graphs or calling AI."""

        from codestrata.application.traceability.merge import merge_finding_traceability

        findings_by_id: dict[str, Finding] = {}
        finding_order: list[str] = []
        evaluated: list[str] = []
        skipped: list[str] = []

        for rule in self._rules:
            if not self._is_applicable(rule, context):
                skipped.append(rule.id())
                continue
            result = rule.evaluate(context)
            evaluated.append(rule.id())
            if result.skipped:
                skipped.append(rule.id())
            for finding in result.findings:
                existing = findings_by_id.get(finding.id)
                if existing is None:
                    findings_by_id[finding.id] = finding
                    finding_order.append(finding.id)
                    continue
                findings_by_id[finding.id] = merge_finding_traceability(existing, finding)
        findings = [findings_by_id[item_id] for item_id in finding_order]

        return RuleEvaluationResult.from_findings(
            findings=tuple(findings),
            rules_evaluated=tuple(evaluated),
            rules_skipped=tuple(skipped),
        )

    def evaluate_pipeline_result(
        self,
        pipeline_result: GraphAssessmentPipelineResult,
    ) -> RuleEvaluationResult:
        """Convenience wrapper around :meth:`evaluate` for pipeline outputs."""

        return self.evaluate(rule_context_from_pipeline(pipeline_result))

    @staticmethod
    def _is_applicable(rule: Rule, context: RuleContext) -> bool:
        supported = rule.supported_languages()
        if not supported:
            return True
        languages = {key.lower() for key in context.bound_keys()}
        # Also consider inventory file languages.
        for entry in context.manifest.files:
            if entry.language:
                languages.add(entry.language.strip().lower())
        return bool(languages.intersection({item.lower() for item in supported}))


def rule_context_from_pipeline(
    pipeline_result: GraphAssessmentPipelineResult,
) -> RuleContext:
    """Build a RuleContext from Phase 2 pipeline outputs."""

    return RuleContext(
        assessment_graph=pipeline_result.assessment_graph,
        repository_graph=pipeline_result.repository_graph,
        knowledge_graph=pipeline_result.knowledge_graph,
        binding_result=pipeline_result.binding_result,
        manifest=pipeline_result.manifest,
    )
