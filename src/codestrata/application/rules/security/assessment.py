"""Opt-in Security Intelligence execution for assessment (Phase 4.5.3).

Runs only when ``[rules] enabled = true`` and ``[rules.security] enabled = true``.
Repository-sensitive evidence must be supplied in-memory. This module never
invokes evidence collectors or re-reads repository files.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.models import RuleRuleResultRecord
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.security.pack import SecurityRulePack
from codestrata.application.rules.security.registration import register_security_pack
from codestrata.application.security.assessment.inventory import SecurityRuleExecutionFact
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
)
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus
from codestrata.domain.rules.models import RuleContext
from codestrata.domain.security.ids import HYGIENE_RULE_IDS
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class SecurityPackExecutionResult(BaseModel):
    """Security pack evaluation plus evidence fingerprints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    repository_sensitive_evidence: AggregatedRepositorySensitiveEvidence | None = None
    evidence_pipeline: str = "not_configured"
    evidence_fingerprint: str = ""
    artifacts_discovered: int = Field(default=0, ge=0)
    configuration_facts_collected: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()
    rule_execution_facts: tuple[SecurityRuleExecutionFact, ...] = ()
    rules_failed: int = Field(default=0, ge=0)


def evaluate_security_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_sensitive_evidence: AggregatedRepositorySensitiveEvidence | None = None,
) -> SecurityPackExecutionResult:
    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_security_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_sensitive_evidence=repository_sensitive_evidence,
    )


def evaluate_security_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_sensitive_evidence: AggregatedRepositorySensitiveEvidence | None = None,
) -> SecurityPackExecutionResult:
    """Evaluate security.core using only the supplied evidence bundle."""

    diagnostics: list[str] = []
    evidence = repository_sensitive_evidence
    evidence_pipeline = "not_configured"
    evidence_fingerprint = ""
    artifacts_discovered = 0
    configuration_facts_collected = 0

    if evidence is None:
        diagnostics.append("repository_sensitive_evidence_unavailable")
    else:
        evidence_pipeline = "repository_sensitive"
        evidence_fingerprint = evidence.evidence_fingerprint or _fingerprint_evidence(
            evidence
        )
        artifacts_discovered = evidence.coverage.candidate_files_discovered
        configuration_facts_collected = evidence.coverage.configuration_facts_collected

    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "repository_sensitive_evidence": evidence,
            "provenance": {
                **shared_context.provenance,
                "security_pack": SecurityRulePack.pack_id,
                "security_pack_version": SecurityRulePack.pack_version,
                "repository_sensitive_evidence_fingerprint": evidence_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "security_enabled": "true",
                "repository_sensitive_evidence_present": str(
                    evidence is not None
                ).lower(),
            },
        }
    )

    registry = RuleRegistry()
    register_security_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.SECURITY
        for record in platform_result.records
    }
    findings = mapper.map_matches(
        platform_result.matches, category_by_rule=category_by_rule
    )
    evaluated = tuple(platform_result.plan.execution_order)
    skipped = tuple(
        entry.rule_id
        for entry in platform_result.plan.skipped
        if entry.rule_id not in evaluated
    )
    for record in platform_result.records:
        if record.status.value == "not_applicable" and record.rule_id not in skipped:
            skipped = (*skipped, record.rule_id)
    evaluation = RuleEvaluationResult.from_findings(
        findings=findings,
        rules_evaluated=evaluated,
        rules_skipped=tuple(sorted(set(skipped))),
    )
    rule_facts = _rule_execution_facts(platform_result.records)
    failed = sum(
        1 for item in rule_facts if item.evaluation_status == "failed"
    )
    return SecurityPackExecutionResult(
        evaluation=evaluation,
        repository_sensitive_evidence=evidence,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint,
        artifacts_discovered=artifacts_discovered,
        configuration_facts_collected=configuration_facts_collected,
        diagnostics=tuple(sorted({item for item in diagnostics if item})),
        rule_execution_facts=rule_facts,
        rules_failed=failed,
    )


def _rule_execution_facts(
    records: Sequence[RuleRuleResultRecord],
) -> tuple[SecurityRuleExecutionFact, ...]:
    facts: list[SecurityRuleExecutionFact] = []
    seen: set[str] = set()
    for record in records:
        rule_id = str(record.rule_id)
        seen.add(rule_id)
        messages: list[str] = []
        if record.evaluation.failure_message:
            messages.append(str(record.evaluation.failure_message)[:400])
        for diagnostic in record.evaluation.diagnostics:
            messages.append(str(diagnostic.message)[:400])
        status = record.status.value
        executed = record.status in {
            RuleResultStatus.MATCHED,
            RuleResultStatus.NOT_MATCHED,
            RuleResultStatus.FAILED,
            RuleResultStatus.SUPPRESSED,
        }
        facts.append(
            SecurityRuleExecutionFact(
                rule_id=rule_id,
                enabled=True,
                executed=executed,
                evaluation_status=status,
                diagnostic_messages=tuple(sorted(set(messages))),
            )
        )
    for rule_id in HYGIENE_RULE_IDS:
        if rule_id in seen:
            continue
        facts.append(
            SecurityRuleExecutionFact(
                rule_id=rule_id,
                enabled=True,
                executed=False,
                evaluation_status="not_executed",
            )
        )
    return tuple(sorted(facts, key=lambda item: item.rule_id))


def security_rules_planned_count() -> int:
    return len(HYGIENE_RULE_IDS)


def _fingerprint_evidence(evidence: AggregatedRepositorySensitiveEvidence) -> str:
    if evidence.evidence_fingerprint:
        return evidence.evidence_fingerprint
    payload = (
        f"{evidence.repository_id}|{evidence.status.value}|"
        f"{len(evidence.artifacts)}|{len(evidence.configuration_facts)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "SecurityPackExecutionResult",
    "evaluate_security_pack_detailed",
    "evaluate_security_pack_for_context_detailed",
    "security_rules_planned_count",
]
