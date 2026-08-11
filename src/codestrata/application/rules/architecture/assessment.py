"""Opt-in Architecture Intelligence execution for assessment (Phase 4.2).

Runs only when ``[rules] enabled = true`` and ``[rules.architecture] enabled = true``.
Findings are produced via RuleExecutionFacade → Shared Rule Platform → Finding mapper
and merged into the legacy RuleEvaluationResult.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.language.factory import (
    create_language_evidence_service,
    language_evidence_pipeline_enabled,
)
from codestrata.application.rules.architecture.pack import ArchitectureRulePack
from codestrata.application.rules.architecture.registration import register_architecture_pack
from codestrata.application.rules.architecture.view_builder import build_architecture_analysis_view
from codestrata.application.rules.facade import (
    RuleExecutionFacade,
    rule_execution_context_from_legacy,
)
from codestrata.application.rules.factory import policy_from_settings
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CodestrataSettings
from codestrata.domain.findings import Finding, RuleEvaluationResult
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.rules.models import RuleContext
from codestrata.services.graph_assessment.results import GraphAssessmentPipelineResult
from codestrata.services.inventory.content_reader import RepositoryContentReader
from codestrata.services.rule_engine.engine import rule_context_from_pipeline


class ArchitecturePackExecutionResult(BaseModel):
    """Architecture pack evaluation plus view fingerprints for assessment assembly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation: RuleEvaluationResult
    graph_fingerprint: str = ""
    extraction_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    classification_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_pipeline: str = "legacy_view_builder"
    evidence_fingerprint: str = ""

def architecture_pack_enabled(settings: CodestrataSettings | None) -> bool:
    if settings is None:
        return False
    return bool(settings.rules.enabled and settings.rules.architecture.enabled)


def evaluate_architecture_pack(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    enterprise_context: object | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> RuleEvaluationResult:
    """Execute architecture.core through the Shared Rule Platform."""

    return evaluate_architecture_pack_detailed(
        pipeline_result=pipeline_result,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        enterprise_context=enterprise_context,
        file_texts=file_texts,
    ).evaluation


def evaluate_architecture_pack_detailed(
    *,
    pipeline_result: GraphAssessmentPipelineResult,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    enterprise_context: object | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> ArchitecturePackExecutionResult:
    """Execute architecture.core and return evaluation plus view fingerprints."""

    legacy_context = rule_context_from_pipeline(pipeline_result)
    return evaluate_architecture_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        enterprise_context=enterprise_context,
        file_texts=file_texts,
    )


def evaluate_architecture_pack_for_context(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    enterprise_context: object | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> RuleEvaluationResult:
    return evaluate_architecture_pack_for_context_detailed(
        legacy_context=legacy_context,
        settings=settings,
        repository_root=repository_root,
        content_reader=content_reader,
        enterprise_context=enterprise_context,
        file_texts=file_texts,
    ).evaluation


def evaluate_architecture_pack_for_context_detailed(
    *,
    legacy_context: RuleContext,
    settings: CodestrataSettings,
    repository_root: Path | None = None,
    content_reader: RepositoryContentReader | None = None,
    enterprise_context: object | None = None,
    file_texts: Mapping[str, str] | None = None,
) -> ArchitecturePackExecutionResult:
    relative_paths = sorted(legacy_context.relative_paths())
    texts = dict(file_texts or {})
    if not texts:
        texts = _load_source_texts(
            relative_paths=relative_paths,
            repository_root=repository_root,
            content_reader=content_reader,
        )
    unit_selection = settings.rules.architecture.unit_selection
    evidence_pipeline = "legacy_view_builder"
    evidence_fingerprint = ""
    if language_evidence_pipeline_enabled(settings):
        evidence_service = create_language_evidence_service(settings)
        evidence_result = evidence_service.collect(
            repository_id=str(
                getattr(legacy_context, "repository_id", None) or "repository"
            ),
            relative_paths=relative_paths,
            file_texts=texts,
            configuration={
                "ignore_path_markers": ",".join(unit_selection.ignore_path_markers),
                "fingerprint": "architecture_assessment",
            },
            build_architecture_view=True,
            module_depth=unit_selection.module_depth,
            composition_root_markers=unit_selection.composition_root_markers,
            registration_markers=unit_selection.registration_markers,
        )
        evidence_pipeline = "language_evidence"
        evidence_fingerprint = str(
            getattr(evidence_result.telemetry, "configuration_fingerprint", "") or ""
        )
        view = evidence_result.architecture_view
        if view is None:
            view = build_architecture_analysis_view(
                relative_paths=relative_paths,
                file_texts=texts,
                module_depth=unit_selection.module_depth,
                composition_root_markers=unit_selection.composition_root_markers,
                registration_markers=unit_selection.registration_markers,
                ignore_path_markers=unit_selection.ignore_path_markers,
            )
    else:
        view = build_architecture_analysis_view(
            relative_paths=relative_paths,
            file_texts=texts,
            module_depth=unit_selection.module_depth,
            composition_root_markers=unit_selection.composition_root_markers,
            registration_markers=unit_selection.registration_markers,
            ignore_path_markers=unit_selection.ignore_path_markers,
        )
    policy = policy_from_settings(settings)
    shared_context = rule_execution_context_from_legacy(legacy_context, policy=policy)
    shared_context = shared_context.model_copy(
        update={
            "architecture_view": view,
            "enterprise_context": enterprise_context
            if enterprise_context is not None
            else shared_context.enterprise_context,
            "provenance": {
                **shared_context.provenance,
                "architecture_pack": ArchitectureRulePack.pack_id,
                "architecture_pack_version": ArchitectureRulePack.pack_version,
                "architecture_graph_fingerprint": view.graph_fingerprint,
            },
            "configuration_facts": {
                **shared_context.configuration_facts,
                "architecture_enabled": "true",
                "coverage_ratio": str(view.coverage_ratio),
            },
        }
    )

    registry = RuleRegistry()
    register_architecture_pack(
        registry,
        settings=settings.rules,
        production=True,
        for_execution=True,
    )
    facade = RuleExecutionFacade(shared_registry=registry)
    platform_result = facade.execute_shared(shared_context)

    mapper = RuleFindingMapper()
    category_by_rule = {
        str(record.rule_id): record.category or RuleCategory.ARCHITECTURE
        for record in platform_result.records
    }
    findings = mapper.map_matches(platform_result.matches, category_by_rule=category_by_rule)
    evaluated = tuple(platform_result.plan.execution_order)
    skipped = tuple(
        entry.rule_id
        for entry in platform_result.plan.skipped
        if entry.rule_id not in evaluated
    )
    # Also treat not-applicable executed rules as skipped for legacy aggregation.
    for record in platform_result.records:
        if record.status.value == "not_applicable" and record.rule_id not in skipped:
            skipped = (*skipped, record.rule_id)
    evaluation = RuleEvaluationResult.from_findings(
        findings=findings,
        rules_evaluated=evaluated,
        rules_skipped=tuple(sorted(set(skipped))),
    )
    return ArchitecturePackExecutionResult(
        evaluation=evaluation,
        graph_fingerprint=view.graph_fingerprint,
        extraction_coverage=view.extraction_coverage,
        classification_coverage=view.classification_coverage,
        evidence_pipeline=evidence_pipeline,
        evidence_fingerprint=evidence_fingerprint,
    )

def merge_rule_evaluations(
    primary: RuleEvaluationResult,
    extra: RuleEvaluationResult,
) -> RuleEvaluationResult:
    """Merge architecture findings into legacy evaluation without dropping either.

    Duplicate finding IDs union EvidenceRefs (Slice 2.2) instead of first-wins.
    """

    from codestrata.application.traceability.merge import merge_finding_traceability

    by_id: dict[str, Finding] = {}
    order: list[str] = []
    for finding in (*primary.findings, *extra.findings):
        existing = by_id.get(finding.id)
        if existing is None:
            by_id[finding.id] = finding
            order.append(finding.id)
            continue
        by_id[finding.id] = merge_finding_traceability(existing, finding)
    return RuleEvaluationResult.from_findings(
        findings=tuple(by_id[item_id] for item_id in order),
        rules_evaluated=tuple(
            sorted(set(primary.rules_evaluated) | set(extra.rules_evaluated))
        ),
        rules_skipped=tuple(sorted(set(primary.rules_skipped) | set(extra.rules_skipped))),
    )


def _load_source_texts(
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
        max_files=max_files,
        max_chars=max_chars,
        max_read_workers=1,
    )
    return texts
