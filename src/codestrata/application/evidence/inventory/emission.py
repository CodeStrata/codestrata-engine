"""Emit stable inventory facts with coverage (E05.2).

Builds on E05.1 observations. Does not execute repository scripts, CI jobs, or
the YAML rule runtime. Missing lockfile is UNKNOWN, not resolved absence.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from codestrata.application.evidence.dependency.composer_collector import (
    collect_composer_dependency_bundle,
)
from codestrata.application.evidence.dependency.gradle_collector import (
    collect_gradle_dependency_bundle,
)
from codestrata.application.evidence.dependency.maven_collector import (
    collect_maven_dependency_bundle,
)
from codestrata.application.evidence.dependency.nuget_collector import (
    collect_nuget_dependency_bundle,
)
from codestrata.application.evidence.dependency.paths import DEFAULT_DEPENDENCY_IGNORE_MARKERS
from codestrata.application.evidence.dependency.python_collector import (
    collect_python_dependency_bundle,
)
from codestrata.application.evidence.inventory.coverage import (
    m01_coverage,
    m02_coverage,
    m03_coverage,
    m04_coverage,
)
from codestrata.application.evidence.inventory.facts import (
    INVENTORY_EMITTER_VERSION,
    INVENTORY_FACT_SCHEMA_VERSION,
    CiInvocationFact,
    ComponentSubjectFact,
    DependencyDeclarationFact,
    DependencyResolutionOccurrence,
    ExtractionStatus,
    FileSubjectFact,
    ImportObservationFact,
    InventoryEvidenceRef,
    InventoryFactBundle,
)
from codestrata.application.evidence.inventory.models import (
    CLASSIFIER_VERSION,
    FileClassificationRecord,
    RepositoryInventorySnapshot,
    ResolutionObservation,
    SupportKind,
)
from codestrata.application.evidence.inventory.npm import collect_npm_facts
from codestrata.application.evidence.inventory.service import ExtractorInventoryService
from codestrata.application.evidence.inventory.surfaces import extract_surfaces
from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.domain.evidence.dependency.enums import DependencyVersionResolutionStatus
from codestrata.domain.evidence.language.identifiers import stable_evidence_id
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass
from codestrata.domain.repository_graph.ids import RepositoryNodeIdFactory
from codestrata.domain.repository_graph.mapping import (
    FileComponentMapping,
    map_files_to_components,
)

_STRUCTURAL_COLLECTORS = (
    collect_maven_dependency_bundle,
    collect_gradle_dependency_bundle,
    collect_python_dependency_bundle,
    collect_composer_dependency_bundle,
    collect_nuget_dependency_bundle,
)


class InventoryFactEmitter:
    """Project inventory observations into versioned facts with coverage."""

    def __init__(self, inventory: ExtractorInventoryService | None = None) -> None:
        self._inventory = inventory or ExtractorInventoryService()

    def emit_tree(
        self,
        repository_root: Path,
        *,
        repository_key: str,
        source_revision: str | None = None,
        max_file_bytes: int = 1_048_576,
    ) -> InventoryFactBundle:
        snapshot = self._inventory.inspect_tree(repository_root, max_file_bytes=max_file_bytes)
        texts = _safe_texts(repository_root, snapshot.files, max_file_bytes=max_file_bytes)
        return self.emit(
            snapshot,
            repository_key=repository_key,
            file_texts=texts,
            source_revision=source_revision,
        )

    def emit(
        self,
        snapshot: RepositoryInventorySnapshot,
        *,
        repository_key: str,
        file_texts: Mapping[str, str],
        source_revision: str | None = None,
    ) -> InventoryFactBundle:
        ids = RepositoryNodeIdFactory(repository_key)
        repository_id = str(ids.repository())
        working_state = _working_state_digest(snapshot.files)
        revision = source_revision or working_state
        evidence: list[InventoryEvidenceRef] = []
        files = _file_facts(ids, snapshot.files, working_state, revision, evidence)
        manifest_dirs = _manifest_directories(snapshot)
        mapping = map_files_to_components(
            tuple(item.relative_path for item in files),
            repository_key=repository_key,
            manifest_directories=manifest_dirs,
        )
        components = _component_facts(mapping)
        declarations, resolutions, decl_errors = _dependency_facts(
            ids,
            snapshot=snapshot,
            file_texts=file_texts,
            working_state=working_state,
            revision=revision,
            evidence=evidence,
        )
        imports = _import_facts(
            repository_key=repository_key,
            snapshot=snapshot,
            file_texts=file_texts,
            evidence=evidence,
            working_state=working_state,
            revision=revision,
        )
        surface_result = extract_surfaces(
            repository_key=repository_key,
            file_texts=file_texts,
            files=snapshot.files,
        )
        surfaces = surface_result.surfaces
        for surface in surfaces:
            evidence.append(
                InventoryEvidenceRef(
                    evidence_id=surface.evidence_id,
                    working_state_digest=working_state,
                    source_revision=revision,
                    relative_path=surface.relative_path,
                    content_digest=_digest_for(snapshot.files, surface.relative_path),
                    extractor_version=INVENTORY_EMITTER_VERSION,
                    line=surface.line,
                    limitation=surface.limitation,
                )
            )
        ci_facts = _ci_facts(ids, snapshot, working_state, revision, evidence)
        unknown_decl = [
            item.declaration_id
            for item in declarations
            if item.resolution is ResolutionObservation.UNKNOWN
        ]
        resolved_decl = [
            item.declaration_id
            for item in declarations
            if item.resolution is ResolutionObservation.RESOLVED
        ]
        eligible_source = sum(
            1
            for item in snapshot.files
            if item.primary_class in {InventoryPrimaryClass.SOURCE, InventoryPrimaryClass.TEST}
            and not item.ignore_reason
            and not item.unread_reason
        )
        coverage = (
            m01_coverage(snapshot.metric),
            m02_coverage(
                declaration_ids=tuple(item.declaration_id for item in declarations),
                resolved_declaration_ids=tuple(resolved_decl),
                unknown_declaration_ids=tuple(unknown_decl),
                error_count=decl_errors,
                resolution_occurrence_count=len(resolutions),
                unsupported_manifest_count=sum(
                    1
                    for item in snapshot.manifests
                    if item.support is SupportKind.DETECTION_ONLY
                    or item.support is SupportKind.UNKNOWN
                ),
            ),
            m03_coverage(
                invocation_count=len(ci_facts),
                unresolved_count=sum(1 for item in ci_facts if item.unresolved),
                documents=len(snapshot.ci),
            ),
            m04_coverage(
                surfaces,
                eligible_source_files=eligible_source,
                parse_failures=len(surface_result.parse_failures),
                unknown_areas=len(surface_result.unknown_areas),
            ),
        )
        limitations = [
            "inventory_envelope_is_engine_local",
            "ci_configuration_is_not_execution",
            "missing_lock_is_not_resolved_absence",
            "no_invented_health_score",
        ]
        if snapshot.metric.status.value == "not_applicable":
            limitations.append("m01_zero_eligible_not_applicable")
        limitations.extend(surface_result.parse_failures)
        limitations.extend(surface_result.unknown_areas)
        return InventoryFactBundle(
            schema_version=INVENTORY_FACT_SCHEMA_VERSION,
            emitter_version=INVENTORY_EMITTER_VERSION,
            repository_id=repository_id,
            repository_key=repository_key,
            source_revision=revision,
            working_state_digest=working_state,
            classification=snapshot.metric,
            files=files,
            components=components,
            file_component_map=mapping,
            declarations=declarations,
            resolutions=resolutions,
            imports=imports,
            surfaces=surfaces,
            ci=ci_facts,
            evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
            coverage=coverage,
            executed_repository_code=False,
            ci_execution_observed=False,
            limitations=tuple(sorted(set(limitations))),
        )


def _file_facts(
    ids: RepositoryNodeIdFactory,
    records: Sequence[FileClassificationRecord],
    working_state: str,
    revision: str,
    evidence: list[InventoryEvidenceRef],
) -> tuple[FileSubjectFact, ...]:
    facts: list[FileSubjectFact] = []
    for record in records:
        if record.relative_path.endswith("/"):
            continue
        try:
            path = normalize_repository_relative_path(record.relative_path)
        except ValueError:
            continue
        subject_id = str(ids.file(path))
        evidence_id = stable_evidence_id("file", path, record.content_digest)
        evidence.append(
            InventoryEvidenceRef(
                evidence_id=evidence_id,
                working_state_digest=working_state,
                source_revision=revision,
                relative_path=path,
                content_digest=record.content_digest,
                extractor_version=CLASSIFIER_VERSION,
                limitation=record.ignore_reason or record.unread_reason,
            )
        )
        facts.append(
            FileSubjectFact(
                subject_id=subject_id,
                relative_path=path,
                primary_class=record.primary_class,
                content_digest=record.content_digest,
                classifier_version=record.classifier_version,
                language=record.language,
                ignore_reason=record.ignore_reason,
                unread_reason=record.unread_reason,
                detected=record.detected,
                structurally_supported=record.structurally_supported,
                evidence_id=evidence_id,
            )
        )
    return tuple(facts)


def _component_facts(
    mapping: Sequence[FileComponentMapping],
) -> tuple[ComponentSubjectFact, ...]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in mapping:
        grouped[(item.component_id, item.component_key)].append(item.file_id)
    facts = [
        ComponentSubjectFact(
            subject_id=component_id,
            component_key=component_key,
            file_ids=tuple(sorted(file_ids)),
        )
        for (component_id, component_key), file_ids in grouped.items()
    ]
    return tuple(sorted(facts, key=lambda item: item.subject_id))


def _manifest_directories(snapshot: RepositoryInventorySnapshot) -> tuple[str, ...]:
    directories: list[str] = []
    for manifest in snapshot.manifests:
        parent = str(PurePosixPath(manifest.relative_path).parent)
        if parent in {"", "."}:
            directories.append("_repository")
        else:
            directories.append(parent)
    return tuple(sorted(set(directories)))


def _dependency_facts(
    ids: RepositoryNodeIdFactory,
    *,
    snapshot: RepositoryInventorySnapshot,
    file_texts: Mapping[str, str],
    working_state: str,
    revision: str,
    evidence: list[InventoryEvidenceRef],
) -> tuple[tuple[DependencyDeclarationFact, ...], tuple[DependencyResolutionOccurrence, ...], int]:
    paths = tuple(
        item.relative_path for item in snapshot.files if not item.relative_path.endswith("/")
    )
    declarations: list[DependencyDeclarationFact] = []
    resolutions: list[DependencyResolutionOccurrence] = []
    errors = 0

    def add_declaration(
        *,
        ecosystem: str,
        coordinate: str,
        namespace: str | None,
        name: str,
        declared_version: str | None,
        manifest_path: str,
        parser_version: str,
        support: SupportKind,
        resolution: ResolutionObservation,
        declaration_id: str,
        duplicate: bool,
        line: int | None,
    ) -> None:
        subject_id = str(ids.dependency(ecosystem=ecosystem, name=name, namespace=namespace))
        evidence_id = declaration_id
        evidence.append(
            InventoryEvidenceRef(
                evidence_id=evidence_id,
                working_state_digest=working_state,
                source_revision=revision,
                relative_path=manifest_path,
                content_digest=_digest_for(snapshot.files, manifest_path),
                extractor_version=parser_version,
                line=line,
            )
        )
        declarations.append(
            DependencyDeclarationFact(
                declaration_id=declaration_id,
                subject_id=subject_id,
                ecosystem=ecosystem,
                coordinate=coordinate,
                declared_version=declared_version,
                direct=True,
                manifest_path=manifest_path,
                parser_version=parser_version,
                support=support,
                resolution=resolution,
                evidence_id=evidence_id,
                duplicate=duplicate,
            )
        )

    for collector in _STRUCTURAL_COLLECTORS:
        bundle = collector(
            relative_paths=paths,
            file_texts=file_texts,
            ignore_path_markers=DEFAULT_DEPENDENCY_IGNORE_MARKERS,
        )
        identities = [item.normalized_identity for item in bundle.declarations]
        duplicates = {identity for identity in identities if identities.count(identity) > 1}
        if bundle.status.value == "failed":
            errors += 1
        pin_resolution = _pin_resolution(bundle.ecosystem.value)
        for declaration in bundle.declarations:
            name, namespace = _split_coordinate(
                bundle.ecosystem.value, declaration.normalized_identity
            )
            add_declaration(
                ecosystem=bundle.ecosystem.value,
                coordinate=declaration.normalized_identity,
                namespace=namespace,
                name=name,
                declared_version=declaration.raw_version,
                manifest_path=declaration.source.path,
                parser_version=bundle.provider_version,
                support=SupportKind.STRUCTURAL,
                resolution=pin_resolution,
                declaration_id=declaration.evidence_id,
                duplicate=declaration.normalized_identity in duplicates,
                line=declaration.source.line_start,
            )
            if (
                declaration.version_resolution_status is DependencyVersionResolutionStatus.RESOLVED
                and declaration.resolved_version_local
                and pin_resolution is ResolutionObservation.RESOLVED
            ):
                occurrence_id = stable_evidence_id(
                    "dependency.resolution",
                    declaration.evidence_id,
                    declaration.resolved_version_local,
                )
                resolutions.append(
                    DependencyResolutionOccurrence(
                        occurrence_id=occurrence_id,
                        declaration_id=declaration.evidence_id,
                        subject_id=str(
                            ids.dependency(
                                ecosystem=bundle.ecosystem.value,
                                name=name,
                                namespace=namespace,
                            )
                        ),
                        ecosystem=bundle.ecosystem.value,
                        resolved_identity=declaration.normalized_identity,
                        resolved_version=declaration.resolved_version_local,
                        lock_path=None,
                        direct=True,
                        evidence_id=occurrence_id,
                    )
                )

    npm_facts = collect_npm_facts(paths, file_texts)
    for item in npm_facts:
        names = [row.name for row in item.declarations]
        dup = {name for name in names if names.count(name) > 1}
        for npm_decl in item.declarations:
            add_declaration(
                ecosystem="npm",
                coordinate=npm_decl.name,
                namespace=None,
                name=npm_decl.name,
                declared_version=npm_decl.declared_range,
                manifest_path=npm_decl.manifest_path,
                parser_version=item.observation.parser_version or "inventory.npm.v1",
                support=item.observation.support,
                resolution=item.observation.resolution,
                declaration_id=npm_decl.declaration_id,
                duplicate=npm_decl.name in dup,
                line=npm_decl.line,
            )
        for occurrence in item.resolutions:
            evidence.append(
                InventoryEvidenceRef(
                    evidence_id=occurrence.occurrence_id,
                    working_state_digest=working_state,
                    source_revision=revision,
                    relative_path=occurrence.lock_path,
                    content_digest=_digest_for(snapshot.files, occurrence.lock_path),
                    extractor_version=item.observation.parser_version or "inventory.npm.v1",
                )
            )
            resolutions.append(
                DependencyResolutionOccurrence(
                    occurrence_id=occurrence.occurrence_id,
                    declaration_id=occurrence.declaration_id,
                    subject_id=str(
                        ids.dependency(ecosystem="npm", name=occurrence.resolved_identity)
                    ),
                    ecosystem="npm",
                    resolved_identity=occurrence.resolved_identity,
                    resolved_version=occurrence.resolved_version,
                    lock_path=occurrence.lock_path,
                    direct=occurrence.direct,
                    evidence_id=occurrence.occurrence_id,
                )
            )

    ordered_decl = tuple(
        sorted(declarations, key=lambda item: (item.manifest_path, item.declaration_id))
    )
    ordered_res = tuple(
        sorted(resolutions, key=lambda item: (item.lock_path or "", item.occurrence_id))
    )
    return ordered_decl, ordered_res, errors


def _import_facts(
    *,
    repository_key: str,
    snapshot: RepositoryInventorySnapshot,
    file_texts: Mapping[str, str],
    evidence: list[InventoryEvidenceRef],
    working_state: str,
    revision: str,
) -> tuple[ImportObservationFact, ...]:
    eligible = [
        item
        for item in snapshot.files
        if item.structurally_supported
        and item.ignore_reason is None
        and item.unread_reason is None
        and not item.relative_path.endswith("/")
    ]
    if not eligible:
        return ()
    paths = tuple(item.relative_path for item in eligible)
    texts = {path: file_texts[path] for path in paths if path in file_texts}
    service = create_language_evidence_service()
    result = service.collect(
        repository_id=repository_key,
        relative_paths=paths,
        file_texts=texts,
        build_architecture_view=False,
    )
    facts: list[ImportObservationFact] = []
    for dependency in result.aggregated.dependencies:
        fact_id = dependency.evidence_id
        facts.append(
            ImportObservationFact(
                fact_id=fact_id,
                source_subject_id=dependency.source_unit_id,
                target_subject_id=dependency.target_unit_id,
                language=dependency.language,
                evidence_paths=dependency.evidence_paths,
                symbols=dependency.symbols,
                evidence_id=fact_id,
                extraction_status=ExtractionStatus.COMPLETE,
            )
        )
        path = dependency.evidence_paths[0] if dependency.evidence_paths else paths[0]
        evidence.append(
            InventoryEvidenceRef(
                evidence_id=fact_id,
                working_state_digest=working_state,
                source_revision=revision,
                relative_path=path,
                content_digest=_digest_for(snapshot.files, path),
                extractor_version=INVENTORY_EMITTER_VERSION,
            )
        )
    return tuple(sorted(facts, key=lambda item: item.fact_id))


def _ci_facts(
    ids: RepositoryNodeIdFactory,
    snapshot: RepositoryInventorySnapshot,
    working_state: str,
    revision: str,
    evidence: list[InventoryEvidenceRef],
) -> tuple[CiInvocationFact, ...]:
    facts: list[CiInvocationFact] = []
    for document in snapshot.ci:
        try:
            subject_id = str(ids.file(document.path))
        except ValueError:
            continue
        for invocation in document.invocations:
            fact_id = stable_evidence_id(
                "ci.invocation",
                document.path,
                invocation.parser_rule,
                invocation.literal_command or "",
                invocation.job or "",
                str(invocation.line or 0),
            )
            facts.append(
                CiInvocationFact(
                    fact_id=fact_id,
                    subject_id=subject_id,
                    path=document.path,
                    line=invocation.line,
                    job=invocation.job,
                    literal_command=invocation.literal_command,
                    condition=invocation.condition,
                    tool_category=invocation.tool_category,
                    target=invocation.target,
                    parser_rule=invocation.parser_rule,
                    unresolved=invocation.unresolved,
                    unresolved_reason=invocation.unresolved_reason,
                    proves_execution=False,
                    evidence_id=fact_id,
                )
            )
            evidence.append(
                InventoryEvidenceRef(
                    evidence_id=fact_id,
                    working_state_digest=working_state,
                    source_revision=revision,
                    relative_path=document.path,
                    content_digest=_digest_for(snapshot.files, document.path),
                    extractor_version=INVENTORY_EMITTER_VERSION,
                    line=invocation.line,
                    limitation="configuration_not_execution",
                )
            )
    return tuple(sorted(facts, key=lambda item: (item.path, item.fact_id)))


def _pin_resolution(ecosystem: str) -> ResolutionObservation:
    if ecosystem in {"maven", "gradle", "python"}:
        return ResolutionObservation.DECLARED_ONLY
    return ResolutionObservation.UNKNOWN


def _split_coordinate(ecosystem: str, identity: str) -> tuple[str, str | None]:
    if ecosystem == "maven" and ":" in identity:
        group, artifact = identity.split(":", 1)
        return artifact, group
    return identity, None


def _digest_for(records: Sequence[FileClassificationRecord], path: str) -> str:
    for item in records:
        if item.relative_path == path:
            return item.content_digest
    return ""


def _working_state_digest(records: Sequence[FileClassificationRecord]) -> str:
    parts = [
        f"{item.relative_path}:{item.content_digest}"
        for item in records
        if not item.relative_path.endswith("/")
    ]
    payload = "\n".join(sorted(parts)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_texts(
    root: Path,
    files: Sequence[FileClassificationRecord],
    *,
    max_file_bytes: int,
) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in files:
        if item.relative_path.endswith("/"):
            continue
        if item.primary_class is InventoryPrimaryClass.BINARY:
            continue
        if item.ignore_reason in {"symlink-escape", "oversize"}:
            continue
        path = root / item.relative_path
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            texts[item.relative_path] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return texts
