"""Build ArchitectureAnalysisView from aggregated language evidence."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.architecture.view_builder import (
    RawPackageFacts,
    finalize_architecture_view,
)
from codestrata.domain.evidence.language.capabilities import DependencySemantics
from codestrata.domain.evidence.language.models import AggregatedLanguageEvidence
from codestrata.domain.rules.architecture.models import (
    ArchitectureAnalysisView,
    ArchitectureFrameworkHit,
)

_SEMANTICS_TO_KIND = {
    DependencySemantics.RUNTIME: "runtime",
    DependencySemantics.TYPE_ONLY: "type_only",
    DependencySemantics.INIT_AGGREGATION: "init_aggregation",
    DependencySemantics.REGISTRATION: "registration",
    DependencySemantics.UNKNOWN: "unknown",
}


def architecture_view_from_aggregated_evidence(
    evidence: AggregatedLanguageEvidence,
    *,
    module_depth: int = 2,
    composition_root_markers: Sequence[str] | None = None,
    registration_markers: Sequence[str] | None = None,
) -> ArchitectureAnalysisView:
    """Convert normalized multi-provider evidence into ArchitectureAnalysisView.

    Language providers supply package-level facts; this adapter applies the same
    primary-unit collapse and dependency normalization as the legacy view builder.
    """

    facts = RawPackageFacts(
        notes=[
            "from_aggregated_language_evidence",
            *evidence.diagnostics,
            *evidence.conflicts,
        ]
    )
    for unit in evidence.source_units:
        facts.package_files[unit.unit_id] = list(unit.paths)
        facts.package_layers[unit.unit_id] = unit.layer_hint
        facts.package_layer_confidence[unit.unit_id] = unit.layer_confidence
        facts.files_considered += unit.file_count
        facts.files_parsed += unit.file_count

    for dep in evidence.dependencies:
        key = (dep.source_unit_id, dep.target_unit_id)
        facts.resolved_edges[key].update(dep.evidence_paths)
        facts.resolved_symbols[key].update(dep.symbols)
        facts.resolved_kinds[key] = _SEMANTICS_TO_KIND.get(dep.semantics, "unknown")

    for hit in evidence.framework_usages:
        facts.framework_hits.append(
            ArchitectureFrameworkHit(
                unit_id=hit.unit_id,
                layer="domain",
                framework=hit.framework_id,
                symbol=hit.symbol,
                path=hit.path,
            )
        )

    # Deduplicate package paths.
    for package_id, paths in list(facts.package_files.items()):
        facts.package_files[package_id] = sorted(set(paths))

    view = finalize_architecture_view(
        facts,
        module_depth=module_depth,
        composition_root_markers=composition_root_markers,
        registration_markers=registration_markers,
    )
    # Preserve contributing providers in normalization notes.
    extra_notes = tuple(
        sorted(
            set(view.normalization_notes)
            | {f"provider:{provider_id}" for provider_id in evidence.contributing_provider_ids}
            | {"evidence_pipeline=language_providers"}
        )
    )
    return view.model_copy(update={"normalization_notes": extra_notes})
