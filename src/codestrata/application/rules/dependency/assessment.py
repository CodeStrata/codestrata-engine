"""Opt-in Dependency Intelligence execution for assessment (Phase 4.4.3).

Runs only when ``[rules] enabled = true`` and ``[rules.dependency] enabled = true``.
Dependency Evidence is collected once (when ``[evidence.dependency] enabled``),
injected into Shared Rule context, and never re-parsed by rules.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.dependency.io import load_dependency_manifest_texts
from codestrata.application.evidence.dependency.service import (
    create_dependency_evidence_service,
)
from codestrata.application.rules.dependency.pack import DependencyRulePack
from codestrata.application.rules.dependency.registration import register_dependency_pack
from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.evidence.dependency.models import AggregatedDependencyEvidence
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.rules.models import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.inventory.content_reader import RepositoryContentReader
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class DependencyPackExecutionResult(BaseModel):
    """Dependency pack evaluation plus evidence fingerprints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    dependency_evidence: AggregatedDependencyEvidence | None = None
    evidence_pipeline: str = "not_configured"
    evidence_fingerprint: str = ""
    manifests_discovered: int = Field(default=0, ge=0)
    manifests_supported: int = Field(default=0, ge=0)
    declarations_collected: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()


def dependency_evidence_collection_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.dependency.enabled)


def evaluate_dependency_pack(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
    dependency_evidence: AggregatedDependencyEvidence | None = None,
) -> RuleEvaluationResult:
    return evaluate_dependency_pack_detailed(
        pipeline_result=pipeline_result,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        file_texts=file_texts,
        dependency_evidence=dependency_evidence,
    ).evaluation


def evaluate_dependency_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
    dependency_evidence: AggregatedDependencyEvidence | None = None,
) -> DependencyPackExecutionResult:
    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_dependency_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        file_texts=file_texts,
        dependency_evidence=dependency_evidence,
    )


def evaluate_dependency_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
    dependency_evidence: AggregatedDependencyEvidence | None = None,
) -> DependencyPackExecutionResult:
    relative_paths = sorted(legacy_context.relative_paths())
    diagnostics: list[str] = []
    evidence = dependency_evidence
    evidence_pipeline = "not_configured"
    evidence_fingerprint = ""
    manifests_discovered = 0
    manifests_supported = 0
    declarations_collected = 0

    if evidence is None and dependency_evidence_collection_enabled(settings):
        texts = dict(file_texts or {})
        if not texts:
            if repository_root is None:
                diagnostics.append("dependency_evidence_missing_repository_root")
            else:
                _paths, texts = load_dependency_manifest_texts(
                    relative_paths=relative_paths,
                    repository_root=repository_root,
                    content_reader=content_reader,
                    max_files=settings.evidence.dependency.max_files,
                    max_chars=settings.evidence.dependency.max_file_chars,
                )
        service = create_dependency_evidence_service(settings)
        repository_id = str(getattr(legacy_context, "repository_id", None) or "repository")
        evidence = service.collect(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=texts,
            configuration_fingerprint="dependency_assessment",
        )
    if evidence is not None:
        evidence_pipeline = "dependency.manifest"
        evidence_fingerprint = evidence.evidence_fingerprint or _fingerprint_evidence(
            evidence
        )
        manifests_discovered = evidence.coverage.manifests_discovered
        manifests_supported = evidence.coverage.manifests_supported
        declarations_collected = evidence.coverage.declarations_collected
        diagnostics.extend(evidence.diagnostics)
    elif not dependency_evidence_collection_enabled(settings):
        diagnostics.append("dependency_evidence_disabled")

    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "dependency_evidence": evidence,
            "provenance": {
                **shared_context.provenance,
                "dependency_pack": DependencyRulePack.pack_id,
                "dependency_pack_version": DependencyRulePack.pack_version,
                "dependency_evidence_fingerprint": evidence_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "dependency_enabled": "true",
                "dependency_evidence_enabled": str(
                    dependency_evidence_collection_enabled(settings)
                ).lower(),
            },
        }
    )

    registry = RuleRegistry()
    register_dependency_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.DEPENDENCY
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
    return DependencyPackExecutionResult(
        evaluation=evaluation,
        dependency_evidence=evidence,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint,
        manifests_discovered=manifests_discovered,
        manifests_supported=manifests_supported,
        declarations_collected=declarations_collected,
        diagnostics=tuple(sorted({item for item in diagnostics if item})),
    )


def _fingerprint_evidence(evidence: AggregatedDependencyEvidence) -> str:
    if evidence.evidence_fingerprint:
        return evidence.evidence_fingerprint
    payload = (
        f"{evidence.repository_id}|{evidence.status.value}|"
        f"{evidence.coverage.declarations_collected}|"
        f"{len(evidence.declarations)}|{len(evidence.manifests)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# Re-export for assessment orchestration symmetry with technical debt.
__all__ = [
    "DependencyPackExecutionResult",
    "dependency_evidence_collection_enabled",
    "evaluate_dependency_pack",
    "evaluate_dependency_pack_detailed",
    "evaluate_dependency_pack_for_context_detailed",
]
