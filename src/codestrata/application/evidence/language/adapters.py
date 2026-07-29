"""Shared helpers that adapt raw package facts into normalized language evidence."""

from __future__ import annotations

from codestrata.application.rules.architecture.view_builder import RawPackageFacts
from codestrata.domain.evidence.language.capabilities import (
    DependencySemantics,
    EvidenceOrigin,
    SourceClassification,
)
from codestrata.domain.evidence.language.capability_catalog import (
    CAP_ARCHITECTURE_LAYERS,
    CAP_ARCHITECTURE_UNITS,
    CAP_DEPENDENCIES_IMPORTS,
    CAP_DEPENDENCIES_TYPE_ONLY,
    CAP_FRAMEWORK_USAGE,
    CAP_SOURCE_FILES,
    CapabilityCoverage,
    ProviderCoverageSummary,
)
from codestrata.domain.evidence.language.models import (
    DependencyEvidence,
    FrameworkUsageEvidence,
    LanguageEvidenceBundle,
    SourceUnitEvidence,
    make_dependency_id,
    make_framework_id,
    make_source_unit_id,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance

_KIND_TO_SEMANTICS = {
    "runtime": DependencySemantics.RUNTIME,
    "type_only": DependencySemantics.TYPE_ONLY,
    "init_aggregation": DependencySemantics.INIT_AGGREGATION,
    "registration": DependencySemantics.REGISTRATION,
    "unknown": DependencySemantics.UNKNOWN,
}


def classify_source_path(path: str) -> SourceClassification:
    """Classify a path for language/evidence layers using shared boundary heuristics."""

    from codestrata.scan_boundary import ScanSourceRole, classify_path_role

    role = classify_path_role(path)
    mapping = {
        ScanSourceRole.PRODUCTION: SourceClassification.SOURCE,
        ScanSourceRole.TEST: SourceClassification.TEST,
        ScanSourceRole.FIXTURE: SourceClassification.FIXTURE,
        ScanSourceRole.EXAMPLE: SourceClassification.EXAMPLE,
        ScanSourceRole.GENERATED: SourceClassification.GENERATED,
        ScanSourceRole.VENDOR: SourceClassification.VENDOR,
        ScanSourceRole.DOCUMENTATION: SourceClassification.DOCUMENTATION,
        ScanSourceRole.UNKNOWN: SourceClassification.UNKNOWN,
        ScanSourceRole.EXCLUDED: SourceClassification.UNKNOWN,
    }
    return mapping.get(role, SourceClassification.UNKNOWN)


def bundle_from_raw_facts(
    *,
    facts: RawPackageFacts,
    provider_id: str,
    provider_version: str,
    language: str,
    configuration_fingerprint: str = "",
) -> LanguageEvidenceBundle:
    provenance_base = EvidenceProvenance(
        provider_id=provider_id,
        provider_version=provider_version,
        source_analyzer="architecture.view_builder.collect_raw_package_facts",
        extraction_method="source_parse",
        origin=EvidenceOrigin.SOURCE_PARSE,
        transformation_chain=("raw_package_facts", "normalized_language_evidence"),
        configuration_fingerprint=configuration_fingerprint,
    )
    source_units: list[SourceUnitEvidence] = []
    for unit_id in sorted(facts.package_files):
        paths = tuple(sorted(set(facts.package_files[unit_id])))
        classifications = {classify_source_path(path) for path in paths}
        if classifications == {SourceClassification.TEST} or classifications == {
            SourceClassification.FIXTURE
        }:
            classification = SourceClassification.TEST
        elif SourceClassification.GENERATED in classifications:
            classification = SourceClassification.GENERATED
        elif SourceClassification.EXAMPLE in classifications:
            classification = SourceClassification.EXAMPLE
        elif SourceClassification.VENDOR in classifications:
            classification = SourceClassification.VENDOR
        elif SourceClassification.DOCUMENTATION in classifications:
            classification = SourceClassification.DOCUMENTATION
        else:
            classification = SourceClassification.SOURCE
        source_units.append(
            SourceUnitEvidence(
                evidence_id=make_source_unit_id(
                    provider_id=provider_id, unit_id=unit_id, language=language
                ),
                unit_id=unit_id,
                language=language,
                paths=paths,
                layer_hint=facts.package_layers.get(unit_id, "unknown"),
                layer_confidence=facts.package_layer_confidence.get(unit_id, "low"),
                classification=classification,
                file_count=len(paths),
                provenance=provenance_base.model_copy(
                    update={"source_path": paths[0] if paths else None}
                ),
            )
        )

    dependencies: list[DependencyEvidence] = []
    for (source, target), path_set in sorted(facts.resolved_edges.items()):
        kind = facts.resolved_kinds.get((source, target), "runtime")
        semantics = _KIND_TO_SEMANTICS.get(kind, DependencySemantics.UNKNOWN)
        symbols = tuple(sorted(facts.resolved_symbols.get((source, target), set())))[:20]
        evidence_paths = tuple(sorted(path_set))[:20]
        dependencies.append(
            DependencyEvidence(
                evidence_id=make_dependency_id(
                    provider_id=provider_id,
                    source=source,
                    target=target,
                    semantics=semantics.value,
                    language=language,
                ),
                source_unit_id=source,
                target_unit_id=target,
                language=language,
                semantics=semantics,
                evidence_paths=evidence_paths,
                symbols=symbols,
                provenance=provenance_base.model_copy(
                    update={"source_path": evidence_paths[0] if evidence_paths else None}
                ),
            )
        )

    framework_usages: list[FrameworkUsageEvidence] = []
    for hit in facts.framework_hits:
        framework_usages.append(
            FrameworkUsageEvidence(
                evidence_id=make_framework_id(
                    provider_id=provider_id,
                    unit_id=hit.unit_id,
                    framework=hit.framework,
                    symbol=hit.symbol,
                    path=hit.path,
                ),
                unit_id=hit.unit_id,
                language=language,
                framework_id=hit.framework,
                symbol=hit.symbol,
                path=hit.path,
                usage_kind="annotation",
                provenance=provenance_base.model_copy(update={"source_path": hit.path}),
            )
        )

    type_only = sum(
        1 for dep in dependencies if dep.semantics is DependencySemantics.TYPE_ONLY
    )
    classified = sum(
        1
        for unit in source_units
        if unit.layer_hint not in {"unknown", "test"} and unit.layer_confidence != "low"
    )
    coverage = ProviderCoverageSummary(
        file_coverage=CapabilityCoverage(
            capability_id=CAP_SOURCE_FILES,
            inputs_considered=facts.files_considered,
            inputs_analyzed=facts.files_parsed,
            inputs_excluded=facts.files_excluded,
            evidence_produced=len(source_units),
        ),
        dependency_coverage=CapabilityCoverage(
            capability_id=CAP_DEPENDENCIES_IMPORTS,
            inputs_considered=facts.files_parsed,
            inputs_analyzed=facts.files_parsed,
            evidence_produced=len(dependencies),
        ),
        unit_coverage=CapabilityCoverage(
            capability_id=CAP_ARCHITECTURE_UNITS,
            inputs_considered=len(source_units),
            inputs_analyzed=len(source_units),
            evidence_produced=len(source_units),
        ),
        layer_coverage=CapabilityCoverage(
            capability_id=CAP_ARCHITECTURE_LAYERS,
            inputs_considered=len(source_units),
            inputs_analyzed=classified,
            evidence_produced=classified,
        ),
        framework_coverage=CapabilityCoverage(
            capability_id=CAP_FRAMEWORK_USAGE,
            inputs_considered=facts.files_parsed,
            inputs_analyzed=facts.files_parsed,
            evidence_produced=len(framework_usages),
        ),
        capabilities=(
            CapabilityCoverage(
                capability_id=CAP_DEPENDENCIES_TYPE_ONLY,
                inputs_considered=len(dependencies),
                inputs_analyzed=type_only,
                evidence_produced=type_only,
            ),
        ),
    )
    return LanguageEvidenceBundle(
        provider_id=provider_id,
        provider_version=provider_version,
        language=language,
        source_units=tuple(source_units),
        dependencies=tuple(dependencies),
        framework_usages=tuple(
            sorted(framework_usages, key=lambda item: (item.unit_id, item.symbol, item.path))
        ),
        coverage=coverage,
        diagnostics=tuple(sorted(set(facts.notes))),
    )
