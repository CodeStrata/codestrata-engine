"""Project language-provider facts into the structural graph without promoting tiers.

Java and JS/TS stay the deepest targets. Python, PHP and C# stay at the
verified retained tier. File detection does not become structural support.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from codestrata.application.evidence.language.providers.depth import (
    JAVASCRIPT_LANGUAGE_PIN,
    LANGUAGE_SUPPORT_PINS,
    pin_for_language,
)
from codestrata.application.evidence.structure.normalize import StructuralNormalizationRequest
from codestrata.domain.contracts.enums import DepthTier
from codestrata.domain.evidence.language.capabilities import DependencySemantics
from codestrata.domain.evidence.language.models import AggregatedLanguageEvidence
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.metrics import (
    DirectionConstraint,
    FrameworkLeakageHit,
    FrameworkSubject,
    ModuleLayer,
)
from codestrata.domain.repository_graph.structural import (
    StructuralConfidence,
    StructuralDepth,
    StructuralEdgeObservation,
    StructuralView,
    looks_absolute_path,
)

_RESOLVED_SEMANTICS = frozenset(
    {
        DependencySemantics.RUNTIME,
        DependencySemantics.REGISTRATION,
        DependencySemantics.INIT_AGGREGATION,
    }
)


class LanguageTierRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    launch_tier: str
    structural_maturity: str
    framework_structural: bool
    provider_id: str
    limitation: str = ""


class LanguageStructureProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request: StructuralNormalizationRequest
    tiers: tuple[LanguageTierRecord, ...]
    excluded_type_only: int
    limitations: tuple[str, ...]


def declared_language_tiers() -> tuple[LanguageTierRecord, ...]:
    """Declared depth only. This does not inspect a repository."""

    rows = [
        LanguageTierRecord(
            language=pin.language,
            launch_tier=pin.launch_tier.value,
            structural_maturity=pin.structural_maturity.value,
            framework_structural=pin.framework_structural,
            provider_id=pin.provider_id,
            limitation=pin.limitations,
        )
        for pin in LANGUAGE_SUPPORT_PINS
    ]
    rows.append(
        LanguageTierRecord(
            language="typescript",
            launch_tier=DepthTier.DEEPEST_TARGET.value,
            structural_maturity=JAVASCRIPT_LANGUAGE_PIN.structural_maturity.value,
            framework_structural=JAVASCRIPT_LANGUAGE_PIN.framework_structural,
            provider_id=JAVASCRIPT_LANGUAGE_PIN.provider_id,
            limitation=(
                "TypeScript is served by the JavaScript provider. File detection "
                "is not a separate structural tier."
            ),
        )
    )
    rows.sort(key=lambda item: item.language)
    return tuple(rows)


def structural_request_from_language(
    evidence: AggregatedLanguageEvidence,
    *,
    direction_constraint: DirectionConstraint | None = None,
) -> LanguageStructureProjection:
    """Admit resolved provider dependencies. Relative unresolved specifiers stay out."""

    observations: list[StructuralEdgeObservation] = []
    layers: list[ModuleLayer] = []
    subjects: list[FrameworkSubject] = []
    hits: list[FrameworkLeakageHit] = []
    module_ids: set[str] = set()
    excluded_type_only = 0
    notes: list[str] = []
    languages: set[str] = set()

    for unit in evidence.source_units:
        languages.add(unit.language)
        module_ids.add(unit.unit_id)
        pin = pin_for_language(unit.language)
        structural = bool(pin and pin.framework_structural)
        subjects.append(
            FrameworkSubject(
                unit_id=unit.unit_id,
                layer=unit.layer_hint,
                layer_confidence=unit.layer_confidence,
                language=unit.language,
                framework_structural=structural,
            )
        )
        if unit.layer_hint not in {"unknown", "test"} and unit.layer_confidence != "low":
            layers.append(ModuleLayer(module_id=unit.unit_id, layer=unit.layer_hint))

    for dep in evidence.dependencies:
        if dep.semantics is DependencySemantics.TYPE_ONLY:
            excluded_type_only += 1
            continue
        path = next(
            (item for item in dep.evidence_paths if item and not looks_absolute_path(item)),
            None,
        )
        unknown = dep.semantics is DependencySemantics.UNKNOWN
        if dep.semantics not in _RESOLVED_SEMANTICS and not unknown:
            continue
        observations.append(
            StructuralEdgeObservation(
                edge_type="imports",
                source_id=dep.source_unit_id,
                target_id=dep.target_unit_id,
                source_type=RepositoryNodeType.MODULE,
                target_type=RepositoryNodeType.MODULE,
                confidence=StructuralConfidence.HIGH,
                depth=StructuralDepth.DIRECT,
                view=StructuralView.RESOLVED,
                unknown=unknown,
                resolved=not unknown,
                evidence_path=path,
            )
        )
        module_ids.add(dep.source_unit_id)
        module_ids.add(dep.target_unit_id)

    for hit in evidence.framework_usages:
        if looks_absolute_path(hit.path):
            continue
        hits.append(
            FrameworkLeakageHit(
                unit_id=hit.unit_id,
                framework=hit.framework_id,
                symbol=hit.symbol,
                path=hit.path,
                language=hit.language,
            )
        )

    if excluded_type_only:
        notes.append("type_only_imports_excluded")
    if "javascript" in languages:
        notes.append("javascript_relative_imports_are_not_structural_edges")
    for language in sorted(languages):
        pin = pin_for_language(language)
        if pin is not None and pin.launch_tier is DepthTier.VERIFIED_RETAINED:
            notes.append(f"lower_tier:{language}")

    request = StructuralNormalizationRequest(
        observations=tuple(observations),
        module_ids=tuple(sorted(module_ids)),
        module_layers=tuple(layers),
        direction_constraint=direction_constraint,
        framework_subjects=tuple(subjects),
        framework_hits=tuple(hits),
        notes=tuple(notes),
    )
    return LanguageStructureProjection(
        request=request,
        tiers=declared_language_tiers(),
        excluded_type_only=excluded_type_only,
        limitations=tuple(notes),
    )


__all__ = [
    "LanguageStructureProjection",
    "LanguageTierRecord",
    "declared_language_tiers",
    "structural_request_from_language",
]
