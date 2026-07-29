"""Opt-in AI Readiness Intelligence execution for assessment (Phase 4.8.3).

Runs only when ``[rules] enabled = true`` and ``[rules.ai_readiness] enabled = true``.
Repository AI-readiness evidence must be supplied in-memory. This module never
invokes evidence collectors or re-reads repository files.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.rules.ai_readiness.pack import AiReadinessRulePack
from codestrata.application.rules.ai_readiness.registration import register_ai_readiness_pack
from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.models import RuleRuleResultRecord
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.ai_readiness.ids import HYGIENE_RULE_IDS
from codestrata.domain.evidence.repository_ai_readiness.models import (
    AggregatedRepositoryAiReadinessEvidence,
)
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus
from codestrata.domain.rules.models import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class AiReadinessRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact (not a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    diagnostic_messages: tuple[str, ...] = ()


class AiReadinessPackExecutionResult(BaseModel):
    """AI Readiness pack evaluation plus evidence fingerprints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    repository_ai_readiness_evidence: AggregatedRepositoryAiReadinessEvidence | None = None
    evidence_pipeline: str = "not_configured"
    evidence_fingerprint: str = ""
    candidate_files_discovered: int = Field(default=0, ge=0)
    technology_count: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()
    rule_execution_facts: tuple[AiReadinessRuleExecutionFact, ...] = ()
    rules_failed: int = Field(default=0, ge=0)


def evaluate_ai_readiness_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_ai_readiness_evidence: (AggregatedRepositoryAiReadinessEvidence | None) = None,
) -> AiReadinessPackExecutionResult:
    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_ai_readiness_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_ai_readiness_evidence=repository_ai_readiness_evidence,
    )


def evaluate_ai_readiness_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_ai_readiness_evidence: (AggregatedRepositoryAiReadinessEvidence | None) = None,
) -> AiReadinessPackExecutionResult:
    """Evaluate ai_readiness.core using only the supplied evidence bundle."""

    diagnostics: list[str] = []
    evidence = repository_ai_readiness_evidence
    evidence_pipeline = "not_configured"
    evidence_fingerprint = ""
    candidate_files_discovered = 0
    technology_count = 0

    if evidence is None:
        diagnostics.append("repository_ai_readiness_evidence_unavailable")
    else:
        evidence_pipeline = "repository_ai_readiness"
        evidence_fingerprint = evidence.evidence_fingerprint or _fingerprint_evidence(evidence)
        candidate_files_discovered = evidence.coverage.candidate_files_discovered
        technology_count = len(evidence.coverage.technologies_represented)

    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "repository_ai_readiness_evidence": evidence,
            "provenance": {
                **shared_context.provenance,
                "ai_readiness_pack": AiReadinessRulePack.pack_id,
                "ai_readiness_pack_version": AiReadinessRulePack.pack_version,
                "repository_ai_readiness_evidence_fingerprint": evidence_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "ai_readiness_enabled": "true",
                "repository_ai_readiness_evidence_present": str(evidence is not None).lower(),
            },
        }
    )

    registry = RuleRegistry()
    register_ai_readiness_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.AI_READINESS
        for record in platform_result.records
    }
    findings = mapper.map_matches(platform_result.matches, category_by_rule=category_by_rule)
    evaluated = tuple(platform_result.plan.execution_order)
    skipped = tuple(
        entry.rule_id for entry in platform_result.plan.skipped if entry.rule_id not in evaluated
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
    failed = sum(1 for item in rule_facts if item.evaluation_status == "failed")
    return AiReadinessPackExecutionResult(
        evaluation=evaluation,
        repository_ai_readiness_evidence=evidence,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint,
        candidate_files_discovered=candidate_files_discovered,
        technology_count=technology_count,
        diagnostics=tuple(sorted({item for item in diagnostics if item})),
        rule_execution_facts=rule_facts,
        rules_failed=failed,
    )


def _rule_execution_facts(
    records: Sequence[RuleRuleResultRecord],
) -> tuple[AiReadinessRuleExecutionFact, ...]:
    facts: list[AiReadinessRuleExecutionFact] = []
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
            AiReadinessRuleExecutionFact(
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
            AiReadinessRuleExecutionFact(
                rule_id=rule_id,
                enabled=True,
                executed=False,
                evaluation_status="not_executed",
            )
        )
    return tuple(sorted(facts, key=lambda item: item.rule_id))


def ai_readiness_rules_planned_count() -> int:
    return len(HYGIENE_RULE_IDS)


def _fingerprint_evidence(evidence: AggregatedRepositoryAiReadinessEvidence) -> str:
    if evidence.evidence_fingerprint:
        return evidence.evidence_fingerprint
    payload = (
        f"{evidence.repository_id}|{evidence.status.value}|"
        f"{len(evidence.file_candidates)}|{len(evidence.api_boundary_facts)}|"
        f"{len(evidence.ai_integration_facts)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "AiReadinessPackExecutionResult",
    "AiReadinessRuleExecutionFact",
    "ai_readiness_rules_planned_count",
    "evaluate_ai_readiness_pack_detailed",
    "evaluate_ai_readiness_pack_for_context_detailed",
]
