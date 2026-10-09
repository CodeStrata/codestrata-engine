"""Generic registered facts for enabled analyzers (E05.3).

Facts are keyed by kind and schema so a consumer or analyzer can read inventory
without importing parser modules. Missing required kinds are UNKNOWN, never an
invented empty success.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.inventory.capability import (
    FACT_KIND_CI,
    FACT_KIND_COMPONENT,
    FACT_KIND_COVERAGE,
    FACT_KIND_DECLARATION,
    FACT_KIND_FILE,
    FACT_KIND_IMPORT,
    FACT_KIND_RESOLUTION,
    FACT_KIND_SURFACE,
)
from codestrata.application.evidence.inventory.facts import (
    CAP_M01,
    CAP_M02,
    CAP_M03,
    CAP_M04,
    ExtractionStatus,
    InventoryFactBundle,
)
from codestrata.application.evidence.inventory.models import SupportKind

REGISTERED_FACT_SCHEMA = "codestrata.inventory.registered_fact.v1"
INVENTORY_ANALYZER_ID = "inventory"

# Fact kinds each enabled analyzer must be able to read from the registry.
ANALYZER_REQUIRED_FACT_KINDS: Mapping[str, frozenset[str]] = {
    INVENTORY_ANALYZER_ID: frozenset(
        {
            FACT_KIND_FILE,
            FACT_KIND_COMPONENT,
            FACT_KIND_DECLARATION,
            FACT_KIND_RESOLUTION,
            FACT_KIND_IMPORT,
            FACT_KIND_SURFACE,
            FACT_KIND_CI,
            FACT_KIND_COVERAGE,
        }
    ),
    "architecture": frozenset({FACT_KIND_FILE, FACT_KIND_SURFACE, FACT_KIND_IMPORT}),
    "dependency": frozenset({FACT_KIND_DECLARATION, FACT_KIND_RESOLUTION}),
    "cicd": frozenset({FACT_KIND_CI}),
    "repository_metrics": frozenset({FACT_KIND_FILE, FACT_KIND_COMPONENT}),
    "security": frozenset({FACT_KIND_FILE}),
}


class RegisteredFact(BaseModel):
    """Parser-neutral fact a downstream analyzer can consume."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = REGISTERED_FACT_SCHEMA
    kind: str
    subject_id: str
    capability_id: str
    extraction_status: ExtractionStatus
    support: SupportKind | None = None
    value: str | None = None
    unit: str | None = None
    evidence_ids: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)


class FactCompatibilityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled_analyzers: tuple[str, ...]
    compatible: bool
    missing_kinds: tuple[str, ...] = ()
    unknown_analyzers: tuple[str, ...] = ()


class InventoryFactIndex(BaseModel):
    """Kind-indexed registered facts. Unknown denominator stays unknown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = REGISTERED_FACT_SCHEMA
    facts: tuple[RegisteredFact, ...] = ()

    def kinds(self) -> frozenset[str]:
        return frozenset(item.kind for item in self.facts)

    def facts_of(self, kind: str) -> tuple[RegisteredFact, ...]:
        return tuple(item for item in self.facts if item.kind == kind)

    def compatible_with(self, enabled_analyzers: Sequence[str]) -> FactCompatibilityReport:
        present = self.kinds()
        missing: list[str] = []
        unknown: list[str] = []
        for analyzer_id in enabled_analyzers:
            required = ANALYZER_REQUIRED_FACT_KINDS.get(analyzer_id)
            if required is None:
                unknown.append(analyzer_id)
                continue
            for kind in sorted(required):
                if kind not in present:
                    missing.append(f"{analyzer_id}:{kind}")
        return FactCompatibilityReport(
            enabled_analyzers=tuple(enabled_analyzers),
            compatible=not missing and not unknown,
            missing_kinds=tuple(missing),
            unknown_analyzers=tuple(unknown),
        )


def register_inventory_facts(bundle: InventoryFactBundle) -> InventoryFactIndex:
    """Project the fact bundle into parser-neutral registered records."""

    facts: list[RegisteredFact] = []
    for file_fact in bundle.files:
        status = ExtractionStatus.COMPLETE
        if file_fact.unread_reason or file_fact.ignore_reason:
            status = ExtractionStatus.UNKNOWN
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_FILE,
                subject_id=file_fact.subject_id,
                capability_id=CAP_M01,
                extraction_status=status,
                support=(
                    SupportKind.STRUCTURAL
                    if file_fact.structurally_supported
                    else SupportKind.DETECTION_ONLY
                    if file_fact.detected
                    else SupportKind.UNKNOWN
                ),
                value=file_fact.primary_class.value,
                evidence_ids=(file_fact.evidence_id,),
                attributes={
                    "relative_path": file_fact.relative_path,
                    "content_digest": file_fact.content_digest,
                    "classifier_version": file_fact.classifier_version,
                },
            )
        )
    for component in bundle.components:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_COMPONENT,
                subject_id=component.subject_id,
                capability_id=CAP_M01,
                extraction_status=ExtractionStatus.COMPLETE,
                value=component.component_key,
                attributes={"file_count": str(len(component.file_ids))},
            )
        )
    for declaration in bundle.declarations:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_DECLARATION,
                subject_id=declaration.subject_id,
                capability_id=CAP_M02,
                extraction_status=ExtractionStatus.COMPLETE,
                support=declaration.support,
                value=declaration.coordinate,
                evidence_ids=(declaration.evidence_id,),
                attributes={
                    "ecosystem": declaration.ecosystem,
                    "resolution": declaration.resolution.value,
                    "manifest_path": declaration.manifest_path,
                    "parser_version": declaration.parser_version,
                },
            )
        )
    for resolution in bundle.resolutions:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_RESOLUTION,
                subject_id=resolution.subject_id,
                capability_id=CAP_M02,
                extraction_status=ExtractionStatus.COMPLETE,
                value=resolution.resolved_identity,
                evidence_ids=(resolution.evidence_id,),
                attributes={
                    "declaration_id": resolution.declaration_id or "",
                    "resolved_version": resolution.resolved_version or "",
                    "lock_path": resolution.lock_path or "",
                    "direct": "true" if resolution.direct else "false",
                },
            )
        )
    for import_fact in bundle.imports:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_IMPORT,
                subject_id=import_fact.source_subject_id,
                capability_id=CAP_M01,
                extraction_status=import_fact.extraction_status,
                value=import_fact.target_subject_id,
                evidence_ids=(import_fact.evidence_id,),
                attributes={"language": import_fact.language or ""},
            )
        )
    for surface in bundle.surfaces:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_SURFACE,
                subject_id=surface.subject_id,
                capability_id=CAP_M04,
                extraction_status=surface.extraction_status,
                support=surface.support,
                value=surface.value,
                evidence_ids=(surface.evidence_id,),
                attributes={
                    "declaration_kind": surface.declaration_kind,
                    "relative_path": surface.relative_path,
                    "line": str(surface.line or ""),
                    "symbol": surface.symbol,
                },
            )
        )
    for invocation in bundle.ci:
        status = ExtractionStatus.UNKNOWN if invocation.unresolved else ExtractionStatus.COMPLETE
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_CI,
                subject_id=invocation.subject_id,
                capability_id=CAP_M03,
                extraction_status=status,
                value=invocation.literal_command,
                evidence_ids=(invocation.evidence_id,),
                attributes={
                    "path": invocation.path,
                    "line": str(invocation.line or ""),
                    "tool_category": invocation.tool_category,
                    "parser_rule": invocation.parser_rule,
                    "proves_execution": "false",
                    "condition": invocation.condition or "",
                },
            )
        )
    for coverage in bundle.coverage:
        facts.append(
            RegisteredFact(
                kind=FACT_KIND_COVERAGE,
                subject_id=coverage.capability_id,
                capability_id=coverage.capability_id,
                extraction_status=ExtractionStatus.COMPLETE,
                value=coverage.coverage_ratio,
                unit="ratio",
                attributes={
                    "evaluated": str(coverage.evaluated),
                    "eligible": str(coverage.eligible),
                    "unknown": str(coverage.unknown),
                    "error": str(coverage.error),
                    "excluded": str(coverage.excluded),
                    "coverage_reason": coverage.coverage_reason or "",
                    "applicability": coverage.applicability.value,
                },
            )
        )
    ordered = tuple(sorted(facts, key=lambda row: (row.kind, row.subject_id, row.value or "")))
    return InventoryFactIndex(facts=_with_kind_placeholders(bundle, ordered))


_KIND_CAPABILITY = {
    FACT_KIND_FILE: CAP_M01,
    FACT_KIND_COMPONENT: CAP_M01,
    FACT_KIND_IMPORT: CAP_M01,
    FACT_KIND_DECLARATION: CAP_M02,
    FACT_KIND_RESOLUTION: CAP_M02,
    FACT_KIND_CI: CAP_M03,
    FACT_KIND_SURFACE: CAP_M04,
    FACT_KIND_COVERAGE: CAP_M01,
}


def _with_kind_placeholders(
    bundle: InventoryFactBundle,
    facts: tuple[RegisteredFact, ...],
) -> tuple[RegisteredFact, ...]:
    """Absent kinds stay registered as NOT_APPLICABLE, never invented success."""

    present = {item.kind for item in facts}
    extras: list[RegisteredFact] = []
    for kind in ANALYZER_REQUIRED_FACT_KINDS[INVENTORY_ANALYZER_ID]:
        if kind in present:
            continue
        extras.append(
            RegisteredFact(
                kind=kind,
                subject_id=bundle.repository_id,
                capability_id=_KIND_CAPABILITY[kind],
                extraction_status=ExtractionStatus.NOT_APPLICABLE,
                attributes={"reason": "no_records_for_kind"},
            )
        )
    if not extras:
        return facts
    combined = [*facts, *extras]
    return tuple(sorted(combined, key=lambda row: (row.kind, row.subject_id, row.value or "")))
