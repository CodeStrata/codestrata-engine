"""Legacy compatibility adapter: existing extractors → normalized evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.language.adapters import bundle_from_raw_facts
from codestrata.application.rules.architecture.view_builder import (
    collect_raw_package_facts,
    finalize_architecture_view,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.models import LanguageEvidenceBundle
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.rules.architecture.models import ArchitectureAnalysisView

LEGACY_ADAPTER_PROVIDER_ID = "language.legacy.adapter"
LEGACY_ADAPTER_VERSION = "1.0.0"


def collect_legacy_evidence_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] | None = None,
    language_filter: str | None = None,
) -> LanguageEvidenceBundle:
    """Produce normalized evidence using the same collectors as the legacy path."""

    facts = collect_raw_package_facts(
        relative_paths=relative_paths,
        file_texts=file_texts,
        ignore_path_markers=ignore_path_markers,
        language_filter=language_filter,
    )
    language = language_filter or "multi"
    bundle = bundle_from_raw_facts(
        facts=facts,
        provider_id=LEGACY_ADAPTER_PROVIDER_ID,
        provider_version=LEGACY_ADAPTER_VERSION,
        language=language,
    )
    # Retag provenance as legacy adapter for inspectability.
    remapped_units = []
    for unit in bundle.source_units:
        remapped_units.append(
            unit.model_copy(
                update={
                    "provenance": _legacy_provenance(unit.provenance.source_path),
                }
            )
        )
    remapped_deps = [
        dep.model_copy(
            update={"provenance": _legacy_provenance(dep.provenance.source_path)}
        )
        for dep in bundle.dependencies
    ]
    remapped_fw = [
        hit.model_copy(update={"provenance": _legacy_provenance(hit.path)})
        for hit in bundle.framework_usages
    ]
    return bundle.model_copy(
        update={
            "source_units": tuple(remapped_units),
            "dependencies": tuple(remapped_deps),
            "framework_usages": tuple(remapped_fw),
            "diagnostics": tuple(
                sorted(set(bundle.diagnostics) | {"legacy_evidence_adapter"})
            ),
        }
    )


def build_view_via_legacy_evidence(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str] | None = None,
    module_depth: int = 2,
    composition_root_markers: Sequence[str] | None = None,
    registration_markers: Sequence[str] | None = None,
    ignore_path_markers: Sequence[str] | None = None,
) -> ArchitectureAnalysisView:
    """Legacy collect → finalize (equivalent to build_architecture_analysis_view)."""

    facts = collect_raw_package_facts(
        relative_paths=relative_paths,
        file_texts=file_texts,
        ignore_path_markers=ignore_path_markers,
    )
    return finalize_architecture_view(
        facts,
        module_depth=module_depth,
        composition_root_markers=composition_root_markers,
        registration_markers=registration_markers,
    )


def _legacy_provenance(source_path: str | None) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=LEGACY_ADAPTER_PROVIDER_ID,
        provider_version=LEGACY_ADAPTER_VERSION,
        source_analyzer="architecture.view_builder",
        extraction_method="legacy_adapter",
        origin=EvidenceOrigin.LEGACY_ADAPTER,
        source_path=source_path,
        transformation_chain=(
            "legacy_collect_raw_package_facts",
            "normalized_language_evidence",
        ),
        notes=("compatibility_path",),
    )
