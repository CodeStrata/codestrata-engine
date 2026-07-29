"""Opt-in Technical Debt Intelligence execution for assessment (Phase 4.3.4).

Runs only when ``[rules] enabled = true`` and ``[rules.technical_debt] enabled = true``.
Complexity evidence is collected once (when ``[evidence.complexity] enabled``),
injected into Shared Rule context, and never re-parsed by rules.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.language.complexity.service import (
    create_complexity_evidence_service,
)
from codestrata.application.rules.architecture.assessment import merge_rule_evaluations
from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.technical_debt.pack import TechnicalDebtRulePack
from codestrata.application.rules.technical_debt.registration import register_technical_debt_pack
from codestrata.application.technical_debt.assessment.factory import technical_debt_pack_enabled
from codestrata.application.technical_debt.evidence.complexity_projection import (
    complexity_evidence_for_debt,
)
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.evidence.language.complexity.models import AggregatedComplexityEvidence
from codestrata.domain.findings import RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.rules.models import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.inventory.content_reader import RepositoryContentReader
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class TechnicalDebtPackExecutionResult(BaseModel):
    """Technical debt pack evaluation plus complexity evidence fingerprints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    complexity_evidence: AggregatedComplexityEvidence | None = None
    evidence_pipeline: str = "not_configured"
    evidence_fingerprint: str = ""
    files_considered: int = Field(default=0, ge=0)
    files_analyzed: int = Field(default=0, ge=0)
    files_excluded: int = Field(default=0, ge=0)
    files_failed: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = ()


def complexity_evidence_collection_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.evidence.complexity.enabled)


def evaluate_technical_debt_pack(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> RuleEvaluationResult:
    return evaluate_technical_debt_pack_detailed(
        pipeline_result=pipeline_result,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        file_texts=file_texts,
    ).evaluation


def evaluate_technical_debt_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> TechnicalDebtPackExecutionResult:
    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        file_texts=file_texts,
    )


def evaluate_technical_debt_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> TechnicalDebtPackExecutionResult:
    relative_paths = sorted(legacy_context.relative_paths())
    diagnostics: list[str] = []
    evidence: AggregatedComplexityEvidence | None = None
    evidence_pipeline = "not_configured"
    evidence_fingerprint = ""
    files_considered = 0
    files_analyzed = 0
    files_excluded = 0
    files_failed = 0

    if complexity_evidence_collection_enabled(settings):
        texts = dict(file_texts or {})
        if not texts:
            texts = _load_complexity_source_texts(
                relative_paths=relative_paths,
                repository_root=repository_root,
                content_reader=content_reader,
                max_files=settings.evidence.complexity.max_files,
                max_chars=settings.evidence.complexity.max_file_chars,
            )
        service = create_complexity_evidence_service(settings)
        repository_id = str(getattr(legacy_context, "repository_id", None) or "repository")
        evidence = complexity_evidence_for_debt(
            service.collect(
                repository_id=repository_id,
                relative_paths=relative_paths,
                file_texts=texts,
                configuration_fingerprint="technical_debt_assessment",
            )
        )
        evidence_pipeline = "language.complexity"
        evidence_fingerprint = _fingerprint_complexity_evidence(evidence)
        files_considered = sum(bundle.files_considered for bundle in evidence.bundles)
        files_analyzed = sum(bundle.files_analyzed for bundle in evidence.bundles)
        files_excluded = sum(bundle.files_excluded for bundle in evidence.bundles)
        files_failed = sum(bundle.files_failed for bundle in evidence.bundles)
        diagnostics.extend(evidence.diagnostics)
    else:
        diagnostics.append("complexity_evidence_disabled")

    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "complexity_evidence": evidence,
            "provenance": {
                **shared_context.provenance,
                "technical_debt_pack": TechnicalDebtRulePack.pack_id,
                "technical_debt_pack_version": TechnicalDebtRulePack.pack_version,
                "complexity_evidence_fingerprint": evidence_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "technical_debt_enabled": "true",
                "complexity_evidence_enabled": str(
                    complexity_evidence_collection_enabled(settings)
                ).lower(),
            },
        }
    )

    registry = RuleRegistry()
    register_technical_debt_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.TECHNICAL_DEBT
        for record in platform_result.records
    }
    findings = mapper.map_matches(platform_result.matches, category_by_rule=category_by_rule)
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
    return TechnicalDebtPackExecutionResult(
        evaluation=evaluation,
        complexity_evidence=evidence,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint,
        files_considered=files_considered,
        files_analyzed=files_analyzed,
        files_excluded=files_excluded,
        files_failed=files_failed,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def _fingerprint_complexity_evidence(evidence: AggregatedComplexityEvidence) -> str:
    parts = [
        evidence.repository_id,
        ",".join(evidence.contributing_provider_ids),
        ",".join(item.evidence_id for item in evidence.files),
        ",".join(item.evidence_id for item in evidence.types),
        ",".join(item.evidence_id for item in evidence.callables),
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _load_complexity_source_texts(
    *,
    relative_paths: Sequence[str],
    repository_root: Path | None,
    content_reader: RepositoryContentReader | None,
    max_files: int = 2000,
    max_chars: int = 100_000,
) -> dict[str, str]:
    from codestrata.application.runtime_performance.file_text_cache import (
        load_shared_source_texts,
    )

    texts, _stats = load_shared_source_texts(
        relative_paths=relative_paths,
        repository_root=repository_root,
        content_reader=content_reader,
        suffixes=(".java", ".py", ".php", ".cs"),
        max_files=max_files,
        max_chars=max_chars,
        max_read_workers=1,
    )
    return texts


__all__ = [
    "TechnicalDebtPackExecutionResult",
    "complexity_evidence_collection_enabled",
    "evaluate_technical_debt_pack",
    "evaluate_technical_debt_pack_detailed",
    "evaluate_technical_debt_pack_for_context_detailed",
    "merge_rule_evaluations",
    "technical_debt_pack_enabled",
]
