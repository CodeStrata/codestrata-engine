"""Application service for language evidence collection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.language.aggregator import LanguageEvidenceAggregator
from codestrata.application.evidence.language.architecture_adapter import (
    architecture_view_from_aggregated_evidence,
)
from codestrata.application.evidence.language.executor import (
    LanguageEvidenceExecutionResult,
    LanguageEvidenceProviderExecutor,
)
from codestrata.application.evidence.language.planner import (
    LanguageEvidencePlan,
    LanguageEvidenceProviderPlanner,
)
from codestrata.application.evidence.language.raw_facts import detect_languages_from_paths
from codestrata.application.evidence.language.registry import LanguageEvidenceProviderRegistry
from codestrata.application.evidence.language.telemetry import (
    LanguageEvidenceTelemetry,
    build_telemetry,
)
from codestrata.domain.evidence.language.contracts import LanguageEvidenceContext
from codestrata.domain.evidence.language.models import AggregatedLanguageEvidence
from codestrata.domain.rules.architecture.models import ArchitectureAnalysisView


class LanguageEvidenceServiceResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: LanguageEvidencePlan
    execution: LanguageEvidenceExecutionResult
    aggregated: AggregatedLanguageEvidence
    telemetry: LanguageEvidenceTelemetry
    architecture_view: ArchitectureAnalysisView | None = None


class LanguageEvidenceService:
    def __init__(
        self,
        registry: LanguageEvidenceProviderRegistry,
        *,
        planner: LanguageEvidenceProviderPlanner | None = None,
        executor: LanguageEvidenceProviderExecutor | None = None,
        aggregator: LanguageEvidenceAggregator | None = None,
        fail_fast: bool = False,
    ) -> None:
        self._registry = registry
        self._planner = planner or LanguageEvidenceProviderPlanner(registry)
        self._executor = executor or LanguageEvidenceProviderExecutor(
            registry, fail_fast=fail_fast
        )
        self._aggregator = aggregator or LanguageEvidenceAggregator()

    @property
    def registry(self) -> LanguageEvidenceProviderRegistry:
        return self._registry

    def list_providers(
        self,
        *,
        language: str | None = None,
        capability: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            _metadata_dict(meta)
            for meta in self._registry.list_providers(
                language=language, capability=capability
            )
        )

    def inspect_provider(self, provider_id: str) -> dict[str, Any]:
        return _metadata_dict(self._registry.get(provider_id).metadata)

    def explain_provider(
        self,
        provider_id: str,
        *,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        context = self.build_context(
            repository_id="inspect",
            relative_paths=relative_paths,
            file_texts=file_texts,
        )
        return self._registry.get(provider_id).explain_applicability(context)

    def plan(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str] | None = None,
        configuration: Mapping[str, str] | None = None,
    ) -> LanguageEvidencePlan:
        context = self.build_context(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            configuration=configuration,
        )
        return self._planner.plan(context)

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str] | None = None,
        configuration: Mapping[str, str] | None = None,
        build_architecture_view: bool = False,
        module_depth: int = 2,
        composition_root_markers: Sequence[str] | None = None,
        registration_markers: Sequence[str] | None = None,
    ) -> LanguageEvidenceServiceResult:
        context = self.build_context(
            repository_id=repository_id,
            relative_paths=relative_paths,
            file_texts=file_texts,
            configuration=configuration,
        )
        plan = self._planner.plan(context)
        execution = self._executor.execute(context, plan)
        aggregated = self._aggregator.aggregate(
            repository_id=repository_id,
            bundles=execution.bundles,
        )
        telemetry = build_telemetry(
            repository_id=repository_id,
            execution=execution,
            aggregated=aggregated,
            configuration_fingerprint=(configuration or {}).get("fingerprint", ""),
        )
        view = None
        if build_architecture_view and aggregated.source_units:
            view = architecture_view_from_aggregated_evidence(
                aggregated,
                module_depth=module_depth,
                composition_root_markers=composition_root_markers,
                registration_markers=registration_markers,
            )
        return LanguageEvidenceServiceResult(
            plan=plan,
            execution=execution,
            aggregated=aggregated,
            telemetry=telemetry,
            architecture_view=view,
        )

    def build_context(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str] | None = None,
        configuration: Mapping[str, str] | None = None,
    ) -> LanguageEvidenceContext:
        texts = dict(file_texts or {})
        paths = tuple(sorted({path.replace("\\", "/") for path in relative_paths}))
        return LanguageEvidenceContext(
            repository_id=repository_id,
            relative_paths=paths,
            file_texts=texts,
            detected_languages=detect_languages_from_paths(paths),
            configuration=dict(configuration or {}),
        )


def _metadata_dict(meta: object) -> dict[str, Any]:
    from codestrata.domain.evidence.language.contracts import LanguageEvidenceProviderMetadata

    assert isinstance(meta, LanguageEvidenceProviderMetadata)
    return {
        "provider_id": str(meta.provider_id),
        "provider_version": meta.provider_version,
        "title": meta.title,
        "description": meta.description,
        "supported_languages": list(meta.supported_languages),
        "supported_file_extensions": list(meta.supported_file_extensions),
        "supported_frameworks": list(meta.supported_frameworks),
        "capabilities_supported": [
            {
                "capability_id": item.capability_id,
                "maturity": str(item.maturity),
                "limitations": item.limitations,
            }
            for item in meta.capabilities.supported
        ],
        "capabilities_unsupported": list(meta.capabilities.unsupported),
        "documentation_reference": meta.documentation_reference,
        "enabled_by_default": meta.enabled_by_default,
    }
