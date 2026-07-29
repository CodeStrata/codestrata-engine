"""Aggregate multi-provider language evidence deterministically."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.evidence.language.capabilities import DependencySemantics
from codestrata.domain.evidence.language.models import (
    AggregatedLanguageEvidence,
    DependencyEvidence,
    FrameworkUsageEvidence,
    LanguageEvidenceBundle,
    SourceUnitEvidence,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance


class LanguageEvidenceAggregator:
    def aggregate(
        self,
        *,
        repository_id: str,
        bundles: Sequence[LanguageEvidenceBundle],
    ) -> AggregatedLanguageEvidence:
        ordered = tuple(
            sorted(bundles, key=lambda item: (item.provider_id, item.language))
        )
        units: dict[str, SourceUnitEvidence] = {}
        deps: dict[str, DependencyEvidence] = {}
        frameworks: dict[str, FrameworkUsageEvidence] = {}
        conflicts: list[str] = []
        diagnostics: list[str] = []
        contributing: list[str] = []

        for bundle in ordered:
            contributing.append(bundle.provider_id)
            diagnostics.extend(bundle.diagnostics)
            for unit in bundle.source_units:
                unit_key = unit.unit_id
                existing_unit = units.get(unit_key)
                if existing_unit is None:
                    units[unit_key] = unit
                    continue
                if (
                    existing_unit.layer_hint != unit.layer_hint
                    and unit.layer_hint != "unknown"
                ):
                    if existing_unit.layer_hint == "unknown":
                        units[unit_key] = unit
                    else:
                        conflicts.append(
                            "unit_layer:"
                            f"{unit_key}:{existing_unit.layer_hint}!={unit.layer_hint}"
                        )
                        units[unit_key] = _merge_unit_provenance(existing_unit, unit)
                else:
                    units[unit_key] = _merge_unit_provenance(existing_unit, unit)

            for dep in bundle.dependencies:
                dep_key = (
                    f"{dep.source_unit_id}->{dep.target_unit_id}:{dep.semantics.value}"
                )
                existing_dep = deps.get(dep_key)
                if existing_dep is None:
                    deps[dep_key] = dep
                    continue
                if existing_dep.semantics != dep.semantics:
                    conflicts.append(
                        "dependency_semantics:"
                        f"{dep_key}:{existing_dep.semantics}!={dep.semantics}"
                    )
                    winner = (
                        dep
                        if _semantics_rank(dep.semantics)
                        > _semantics_rank(existing_dep.semantics)
                        else existing_dep
                    )
                    other = existing_dep if winner is dep else dep
                    deps[dep_key] = _merge_dep_provenance(winner, other)
                else:
                    deps[dep_key] = _merge_dep_provenance(existing_dep, dep)

            for hit in bundle.framework_usages:
                fw_key = f"{hit.unit_id}:{hit.framework_id}:{hit.symbol}:{hit.path}"
                existing_fw = frameworks.get(fw_key)
                if existing_fw is None:
                    frameworks[fw_key] = hit
                else:
                    frameworks[fw_key] = hit

        return AggregatedLanguageEvidence(
            repository_id=repository_id,
            bundles=ordered,
            source_units=tuple(sorted(units.values(), key=lambda item: item.unit_id)),
            dependencies=tuple(
                sorted(
                    deps.values(),
                    key=lambda item: (
                        item.source_unit_id,
                        item.target_unit_id,
                        item.semantics.value,
                    ),
                )
            ),
            framework_usages=tuple(
                sorted(
                    frameworks.values(),
                    key=lambda item: (item.unit_id, item.framework_id, item.symbol, item.path),
                )
            ),
            conflicts=tuple(sorted(set(conflicts))),
            diagnostics=tuple(sorted(set(diagnostics))),
            contributing_provider_ids=tuple(sorted(set(contributing))),
        )


def _semantics_rank(value: DependencySemantics) -> int:
    return {
        DependencySemantics.RUNTIME: 4,
        DependencySemantics.REGISTRATION: 3,
        DependencySemantics.INIT_AGGREGATION: 2,
        DependencySemantics.TYPE_ONLY: 1,
        DependencySemantics.UNKNOWN: 0,
    }.get(value, 0)


def _merge_unit_provenance(
    left: SourceUnitEvidence,
    right: SourceUnitEvidence,
) -> SourceUnitEvidence:
    chain = tuple(
        sorted(
            set(left.provenance.transformation_chain)
            | set(right.provenance.transformation_chain)
            | {f"merged_from:{right.provenance.provider_id}"}
        )
    )
    notes = tuple(
        sorted(
            set(left.provenance.notes) | set(right.provenance.notes) | {"multi_provider"}
        )
    )
    provenance = EvidenceProvenance(
        provider_id=left.provenance.provider_id,
        provider_version=left.provenance.provider_version,
        source_analyzer=left.provenance.source_analyzer,
        extraction_method=left.provenance.extraction_method,
        origin=left.provenance.origin,
        source_path=left.provenance.source_path,
        transformation_chain=chain,
        configuration_fingerprint=left.provenance.configuration_fingerprint,
        notes=notes,
    )
    paths = tuple(sorted(set(left.paths) | set(right.paths)))
    return left.model_copy(
        update={
            "paths": paths,
            "file_count": max(left.file_count, right.file_count, len(paths)),
            "provenance": provenance,
        }
    )


def _merge_dep_provenance(
    left: DependencyEvidence,
    right: DependencyEvidence,
) -> DependencyEvidence:
    chain = tuple(
        sorted(
            set(left.provenance.transformation_chain)
            | set(right.provenance.transformation_chain)
            | {f"merged_from:{right.provenance.provider_id}"}
        )
    )
    notes = tuple(
        sorted(
            set(left.provenance.notes) | set(right.provenance.notes) | {"multi_provider"}
        )
    )
    provenance = EvidenceProvenance(
        provider_id=left.provenance.provider_id,
        provider_version=left.provenance.provider_version,
        source_analyzer=left.provenance.source_analyzer,
        extraction_method=left.provenance.extraction_method,
        origin=left.provenance.origin,
        source_path=left.provenance.source_path,
        transformation_chain=chain,
        configuration_fingerprint=left.provenance.configuration_fingerprint,
        notes=notes,
    )
    return left.model_copy(
        update={
            "evidence_paths": tuple(
                sorted(set(left.evidence_paths) | set(right.evidence_paths))
            ),
            "symbols": tuple(sorted(set(left.symbols) | set(right.symbols))),
            "provenance": provenance,
        }
    )
