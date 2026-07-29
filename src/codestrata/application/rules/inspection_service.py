"""Deterministic explainability for Shared Rule Platform."""

from __future__ import annotations

from codestrata.application.rules.finding_mapper import explain_finding_identity
from codestrata.application.rules.models import (
    RuleExecutionPlan,
    RuleExplanation,
    RulePlatformExecutionResult,
)
from codestrata.application.rules.registry import RuleRegistry
from codestrata.domain.rules.results import RuleMatch


class RuleInspectionService:
    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def explain_metadata(self, rule_id: str) -> RuleExplanation:
        meta = self._registry.metadata_for(rule_id)
        return RuleExplanation(
            subject=rule_id,
            reason_code="rule_metadata",
            message=meta.description,
            details={
                "title": meta.title,
                "version": str(meta.version),
                "category": meta.category.value,
                "default_severity": meta.default_severity.value,
                "enabled_by_default": str(meta.enabled_by_default),
                "requires_enterprise_context": str(meta.requires_enterprise_context),
            },
        )

    def explain_plan(self, plan: RuleExecutionPlan) -> tuple[RuleExplanation, ...]:
        explanations: list[RuleExplanation] = []
        for rule_id in plan.execution_order:
            explanations.append(
                RuleExplanation(
                    subject=rule_id,
                    reason_code="selected",
                    message="Rule selected for deterministic execution",
                    details={
                        "incremental_mode": plan.incremental_mode,
                        "reuse_claimed": str(plan.reuse_claimed),
                    },
                )
            )
        for skipped in plan.skipped:
            explanations.append(
                RuleExplanation(
                    subject=skipped.rule_id,
                    reason_code=(skipped.skip_reason.value if skipped.skip_reason else "skipped"),
                    message=skipped.message or "Rule skipped",
                    details={
                        "invalidation_fingerprint": skipped.invalidation_fingerprint or "",
                    },
                )
            )
        return tuple(sorted(explanations, key=lambda item: (item.subject, item.reason_code)))

    def explain_result(self, result: RulePlatformExecutionResult) -> tuple[RuleExplanation, ...]:
        explanations: list[RuleExplanation] = []
        for record in result.records:
            explanations.append(
                RuleExplanation(
                    subject=record.rule_id,
                    reason_code=record.status.value,
                    message=record.evaluation.failure_message
                    or (
                        record.evaluation.skip_reason.value
                        if record.evaluation.skip_reason
                        else record.status.value
                    ),
                    details={
                        "match_count": str(len(record.evaluation.matches)),
                        "suppression": (
                            record.evaluation.suppression.suppression_id
                            if record.evaluation.suppression
                            else ""
                        ),
                    },
                )
            )
        for match in result.suppressed_matches:
            explanations.append(
                RuleExplanation(
                    subject=str(match.rule_id),
                    reason_code="suppressed_match",
                    message="Match retained for inspection but suppressed from findings",
                    details=explain_finding_identity(match),
                )
            )
        return tuple(sorted(explanations, key=lambda item: (item.subject, item.reason_code)))

    def explain_finding_identity(self, match: RuleMatch) -> RuleExplanation:
        details = explain_finding_identity(match)
        return RuleExplanation(
            subject=str(match.rule_id),
            reason_code="finding_identity",
            message="Finding ID derived from rule ID and sorted subject keys",
            details=details,
        )
