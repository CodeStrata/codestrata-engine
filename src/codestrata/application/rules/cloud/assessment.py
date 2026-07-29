"""Opt-in Cloud Intelligence execution for assessment (Phase 4.7.3).

Runs only when ``[rules] enabled = true`` and ``[rules.cloud] enabled = true``.
Repository-cloud evidence must be supplied in-memory. This module never
invokes evidence collectors or re-reads repository files.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.rules.cloud.pack import CloudRulePack
from codestrata.application.rules.cloud.registration import register_cloud_pack
from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.models import RuleRuleResultRecord
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.cloud.ids import HYGIENE_RULE_IDS
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
)
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus
from codestrata.domain.rules.models import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class CloudRuleExecutionFact(BaseModel):
    """Bounded per-rule execution fact (not a Finding)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    enabled: bool = True
    executed: bool = False
    evaluation_status: str = "not_executed"
    diagnostic_messages: tuple[str, ...] = ()


class CloudPackExecutionResult(BaseModel):
    """Cloud pack evaluation plus evidence fingerprints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    repository_cloud_evidence: AggregatedRepositoryCloudEvidence | None = None
    evidence_pipeline: str = "not_configured"
    evidence_fingerprint: str = ""
    candidate_files_discovered: int = Field(default=0, ge=0)
    technology_count: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()
    rule_execution_facts: tuple[CloudRuleExecutionFact, ...] = ()
    rules_failed: int = Field(default=0, ge=0)


def evaluate_cloud_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_cloud_evidence: AggregatedRepositoryCloudEvidence | None = None,
) -> CloudPackExecutionResult:
    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_cloud_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_cloud_evidence=repository_cloud_evidence,
    )


def evaluate_cloud_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_cloud_evidence: AggregatedRepositoryCloudEvidence | None = None,
) -> CloudPackExecutionResult:
    """Evaluate cloud.core using only the supplied evidence bundle."""

    diagnostics: list[str] = []
    evidence = repository_cloud_evidence
    evidence_pipeline = "not_configured"
    evidence_fingerprint = ""
    candidate_files_discovered = 0
    technology_count = 0

    if evidence is None:
        diagnostics.append("repository_cloud_evidence_unavailable")
    else:
        evidence_pipeline = "repository_cloud"
        evidence_fingerprint = evidence.evidence_fingerprint or _fingerprint_evidence(evidence)
        candidate_files_discovered = evidence.coverage.candidate_files_discovered
        technology_count = len(evidence.coverage.technologies_represented)

    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "repository_cloud_evidence": evidence,
            "provenance": {
                **shared_context.provenance,
                "cloud_pack": CloudRulePack.pack_id,
                "cloud_pack_version": CloudRulePack.pack_version,
                "repository_cloud_evidence_fingerprint": evidence_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "cloud_enabled": "true",
                "repository_cloud_evidence_present": str(evidence is not None).lower(),
            },
        }
    )

    registry = RuleRegistry()
    register_cloud_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.CLOUD
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
    return CloudPackExecutionResult(
        evaluation=evaluation,
        repository_cloud_evidence=evidence,
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
) -> tuple[CloudRuleExecutionFact, ...]:
    facts: list[CloudRuleExecutionFact] = []
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
            CloudRuleExecutionFact(
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
            CloudRuleExecutionFact(
                rule_id=rule_id,
                enabled=True,
                executed=False,
                evaluation_status="not_executed",
            )
        )
    return tuple(sorted(facts, key=lambda item: item.rule_id))


def cloud_rules_planned_count() -> int:
    return len(HYGIENE_RULE_IDS)


def _fingerprint_evidence(evidence: AggregatedRepositoryCloudEvidence) -> str:
    if evidence.evidence_fingerprint:
        return evidence.evidence_fingerprint
    payload = (
        f"{evidence.repository_id}|{evidence.status.value}|"
        f"{len(evidence.file_candidates)}|{len(evidence.platform_facts)}|"
        f"{len(evidence.container_facts)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "CloudPackExecutionResult",
    "CloudRuleExecutionFact",
    "cloud_rules_planned_count",
    "evaluate_cloud_pack_detailed",
    "evaluate_cloud_pack_for_context_detailed",
]
