"""Collect aggregated repository performance evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.repository_performance.discovery import (
    DEFAULT_IGNORE_MARKERS,
    discover_performance_candidates,
    normalize_relative_path,
)
from codestrata.application.evidence.repository_performance.inspectors import (
    ContentHit,
    inspect_blocking_text,
    inspect_caching_text,
    inspect_concurrency_text,
    inspect_configuration_text,
    inspect_data_text,
    inspect_dependency_manifest_text,
    inspect_frontend_text,
    inspect_observability_text,
    inspect_resource_text,
)
from codestrata.application.evidence.repository_performance.limitations import (
    standard_limitations,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_performance.enums import (
    EvidenceConfirmationLevel,
    PerformanceEvidenceFamily,
    RepositoryPerformanceParseStatus,
)
from codestrata.domain.evidence.repository_performance.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    evidence_bundle_fingerprint,
    make_blocking_evidence_id,
    make_bundle_id,
    make_cache_evidence_id,
    make_concurrency_evidence_id,
    make_config_evidence_id,
    make_data_evidence_id,
    make_diagnostic_id,
    make_file_evidence_id,
    make_frontend_evidence_id,
    make_obs_evidence_id,
    make_resource_evidence_id,
)
from codestrata.domain.evidence.repository_performance.models import (
    AggregatedRepositoryPerformanceEvidence,
    PerformanceBlockingFactEvidence,
    PerformanceCachingFactEvidence,
    PerformanceConcurrencyFactEvidence,
    PerformanceConfigurationFactEvidence,
    PerformanceDataAccessFactEvidence,
    PerformanceFileCandidateEvidence,
    PerformanceFrontendFactEvidence,
    PerformanceObservabilityFactEvidence,
    PerformanceResourceFactEvidence,
    RepositoryPerformanceDiagnostic,
    RepositoryPerformanceEvidenceCoverage,
)

_SOURCE_SUFFIXES = frozenset({".java", ".py", ".ts", ".tsx", ".js", ".cs"})


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_performance_discovery",
        extraction_method="path_convention",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _diagnostic(*, code: str, message: str, path: str | None) -> RepositoryPerformanceDiagnostic:
    return RepositoryPerformanceDiagnostic(
        diagnostic_id=make_diagnostic_id(code=code, path=path or "", detail=message),
        diagnostic_code=code,
        message=message,
        origin="orchestration",
        path=path,
    )


def _dedupe_by_id[T](items: Sequence[T], *, id_attr: str = "evidence_id") -> tuple[T, ...]:
    seen: set[str] = set()
    ordered: list[T] = []
    for item in sorted(items, key=lambda value: str(getattr(value, id_attr))):
        evidence_id = str(getattr(item, id_attr))
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        ordered.append(item)
    return tuple(ordered)


def _apply_hit_technologies(hit: ContentHit, technologies: set[str]) -> None:
    technologies.update(hit.technologies)
    for kind in (
        hit.data_kind,
        hit.blocking_kind,
        hit.caching_kind,
        hit.concurrency_kind,
        hit.resource_kind,
        hit.frontend_kind,
        hit.obs_kind,
        hit.config_kind,
    ):
        if kind is not None:
            technologies.add(kind.value)


def collect_repository_performance_evidence(
    *,
    repository_id: str,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    load_errors: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    configuration_fingerprint: str = "",
) -> AggregatedRepositoryPerformanceEvidence:
    """Collect deterministic repository performance evidence (no Findings)."""

    errors = dict(load_errors or {})
    texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
    candidates = discover_performance_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    diagnostics: list[RepositoryPerformanceDiagnostic] = []
    file_candidates: list[PerformanceFileCandidateEvidence] = []
    data_facts: list[PerformanceDataAccessFactEvidence] = []
    blocking_facts: list[PerformanceBlockingFactEvidence] = []
    caching_facts: list[PerformanceCachingFactEvidence] = []
    concurrency_facts: list[PerformanceConcurrencyFactEvidence] = []
    resource_facts: list[PerformanceResourceFactEvidence] = []
    frontend_facts: list[PerformanceFrontendFactEvidence] = []
    obs_facts: list[PerformanceObservabilityFactEvidence] = []
    config_facts: list[PerformanceConfigurationFactEvidence] = []

    inspected = 0
    confirmed = 0
    unsupported = 0
    malformed = 0
    skipped = 0
    technologies: set[str] = set()
    families: set[str] = set()

    for candidate in candidates:
        path = candidate.path
        families.add(candidate.family.value)
        technologies.update(candidate.technology_hints)
        confirmation = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
        bases = list(candidate.discovery_bases)
        detail: str | None = None
        line_hints: tuple[int, ...] = ()
        hits: list[ContentHit] = []

        if path in errors:
            code = errors[path]
            if code == "file_too_large":
                skipped += 1
                confirmation = EvidenceConfirmationLevel.SKIPPED
            elif code in {"unsupported_encoding", "unreadable_file"}:
                unsupported += 1
                confirmation = EvidenceConfirmationLevel.UNSUPPORTED
            elif code == "truncated_parsing":
                malformed += 0
            else:
                unsupported += 1
                confirmation = EvidenceConfirmationLevel.UNSUPPORTED
            diagnostics.append(
                _diagnostic(
                    code=code,
                    message=f"Candidate could not be fully inspected ({code}).",
                    path=path,
                )
            )

        text = texts.get(path)
        primary_hit: ContentHit | None = None
        if text is not None:
            inspected += 1
            if candidate.dependency_manifest:
                hits = inspect_dependency_manifest_text(text)
            elif candidate.family is PerformanceEvidenceFamily.DATA_ACCESS:
                primary_hit = inspect_data_text(text, kind=candidate.data_kind)
            elif candidate.family is PerformanceEvidenceFamily.BLOCKING_OPERATIONS:
                primary_hit = inspect_blocking_text(text, kind=candidate.blocking_kind)
            elif candidate.family is PerformanceEvidenceFamily.CACHING:
                primary_hit = inspect_caching_text(text, kind=candidate.caching_kind)
            elif candidate.family is PerformanceEvidenceFamily.CONCURRENCY_ASYNC:
                primary_hit = inspect_concurrency_text(text, kind=candidate.concurrency_kind)
            elif candidate.family is PerformanceEvidenceFamily.RESOURCE_MANAGEMENT:
                primary_hit = inspect_resource_text(text, kind=candidate.resource_kind)
            elif candidate.family is PerformanceEvidenceFamily.FRONTEND_PERFORMANCE:
                primary_hit = inspect_frontend_text(text, kind=candidate.frontend_kind)
            elif candidate.family is PerformanceEvidenceFamily.OBSERVABILITY_PROFILING:
                primary_hit = inspect_observability_text(text, kind=candidate.obs_kind)
            elif candidate.family is PerformanceEvidenceFamily.CONFIGURATION_CONTROLS:
                primary_hit = inspect_configuration_text(text, kind=candidate.config_kind)
            elif candidate.family is PerformanceEvidenceFamily.UNKNOWN:
                hits = inspect_dependency_manifest_text(text)

            if primary_hit is not None:
                hits = [primary_hit]

            # Cross-inspect blocking markers on other-family source candidates.
            suffix = PurePosixPath(path).suffix.lower()
            if (
                suffix in _SOURCE_SUFFIXES
                and candidate.family is not PerformanceEvidenceFamily.BLOCKING_OPERATIONS
            ):
                blocking_hit = inspect_blocking_text(text, kind=None)
                if (
                    blocking_hit is not None
                    and blocking_hit.confirmation_level
                    is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
                ):
                    hits.append(blocking_hit)
                    families.add(PerformanceEvidenceFamily.BLOCKING_OPERATIONS.value)

            for hit in hits:
                _apply_hit_technologies(hit, technologies)
                if hit.confirmation_level is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED:
                    if confirmation is not EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED:
                        confirmation = hit.confirmation_level
                        detail = hit.detail
                        line_hints = hit.line_hints
                    bases.extend(hit.discovery_bases)
                elif confirmation is EvidenceConfirmationLevel.DISCOVERED_CANDIDATE:
                    confirmation = hit.confirmation_level
                    detail = hit.detail
                    line_hints = hit.line_hints

            if confirmation is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED:
                confirmed += 1

        unique_bases = tuple(dict.fromkeys(bases))
        file_candidates.append(
            PerformanceFileCandidateEvidence(
                evidence_id=make_file_evidence_id(path=path, family=candidate.family.value),
                path=path,
                family=candidate.family,
                confirmation_level=confirmation,
                discovery_bases=unique_bases,
                technology_hints=tuple(sorted(set(candidate.technology_hints))),
                size_bytes=len(text.encode("utf-8")) if text is not None else None,
                provenance=_provenance(path, configuration_fingerprint=configuration_fingerprint),
                metadata={"detail": detail} if detail else {},
            )
        )

        basis = unique_bases[0].value if unique_bases else "path"
        for hit in hits:
            data_kind = hit.data_kind or (candidate.data_kind if hit is primary_hit else None)
            blocking_kind = hit.blocking_kind or (
                candidate.blocking_kind if hit is primary_hit else None
            )
            caching_kind = hit.caching_kind or (
                candidate.caching_kind if hit is primary_hit else None
            )
            concurrency_kind = hit.concurrency_kind or (
                candidate.concurrency_kind if hit is primary_hit else None
            )
            resource_kind = hit.resource_kind or (
                candidate.resource_kind if hit is primary_hit else None
            )
            frontend_kind = hit.frontend_kind or (
                candidate.frontend_kind if hit is primary_hit else None
            )
            obs_kind = hit.obs_kind or (candidate.obs_kind if hit is primary_hit else None)
            config_kind = hit.config_kind or (candidate.config_kind if hit is primary_hit else None)
            hit_confirmation = hit.confirmation_level
            hit_bases = tuple(dict.fromkeys([*unique_bases, *hit.discovery_bases]))
            hit_basis = hit_bases[0].value if hit_bases else basis

            if data_kind is not None:
                families.add(PerformanceEvidenceFamily.DATA_ACCESS.value)
                data_facts.append(
                    PerformanceDataAccessFactEvidence(
                        evidence_id=make_data_evidence_id(
                            kind=data_kind.value, path=path, basis=hit_basis
                        ),
                        kind=data_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if blocking_kind is not None:
                families.add(PerformanceEvidenceFamily.BLOCKING_OPERATIONS.value)
                blocking_facts.append(
                    PerformanceBlockingFactEvidence(
                        evidence_id=make_blocking_evidence_id(
                            kind=blocking_kind.value, path=path, basis=hit_basis
                        ),
                        kind=blocking_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if caching_kind is not None:
                families.add(PerformanceEvidenceFamily.CACHING.value)
                caching_facts.append(
                    PerformanceCachingFactEvidence(
                        evidence_id=make_cache_evidence_id(
                            kind=caching_kind.value, path=path, basis=hit_basis
                        ),
                        kind=caching_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if concurrency_kind is not None:
                families.add(PerformanceEvidenceFamily.CONCURRENCY_ASYNC.value)
                concurrency_facts.append(
                    PerformanceConcurrencyFactEvidence(
                        evidence_id=make_concurrency_evidence_id(
                            kind=concurrency_kind.value, path=path, basis=hit_basis
                        ),
                        kind=concurrency_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if resource_kind is not None:
                families.add(PerformanceEvidenceFamily.RESOURCE_MANAGEMENT.value)
                resource_facts.append(
                    PerformanceResourceFactEvidence(
                        evidence_id=make_resource_evidence_id(
                            kind=resource_kind.value, path=path, basis=hit_basis
                        ),
                        kind=resource_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if frontend_kind is not None:
                families.add(PerformanceEvidenceFamily.FRONTEND_PERFORMANCE.value)
                frontend_facts.append(
                    PerformanceFrontendFactEvidence(
                        evidence_id=make_frontend_evidence_id(
                            kind=frontend_kind.value, path=path, basis=hit_basis
                        ),
                        kind=frontend_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if obs_kind is not None:
                families.add(PerformanceEvidenceFamily.OBSERVABILITY_PROFILING.value)
                obs_facts.append(
                    PerformanceObservabilityFactEvidence(
                        evidence_id=make_obs_evidence_id(
                            kind=obs_kind.value, path=path, basis=hit_basis
                        ),
                        kind=obs_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if config_kind is not None:
                families.add(PerformanceEvidenceFamily.CONFIGURATION_CONTROLS.value)
                config_facts.append(
                    PerformanceConfigurationFactEvidence(
                        evidence_id=make_config_evidence_id(
                            kind=config_kind.value, path=path, basis=hit_basis
                        ),
                        kind=config_kind,
                        path=path,
                        confirmation_level=hit_confirmation,
                        discovery_bases=hit_bases,
                        detail=hit.detail,
                        line_hints=hit.line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )

        # Emit path-discovered kinds even when content was absent / unconfirmed.
        if not hits:
            data_kind = candidate.data_kind
            blocking_kind = candidate.blocking_kind
            caching_kind = candidate.caching_kind
            concurrency_kind = candidate.concurrency_kind
            resource_kind = candidate.resource_kind
            frontend_kind = candidate.frontend_kind
            obs_kind = candidate.obs_kind
            config_kind = candidate.config_kind
            if data_kind is not None:
                data_facts.append(
                    PerformanceDataAccessFactEvidence(
                        evidence_id=make_data_evidence_id(
                            kind=data_kind.value, path=path, basis=basis
                        ),
                        kind=data_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if blocking_kind is not None:
                blocking_facts.append(
                    PerformanceBlockingFactEvidence(
                        evidence_id=make_blocking_evidence_id(
                            kind=blocking_kind.value, path=path, basis=basis
                        ),
                        kind=blocking_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if caching_kind is not None:
                caching_facts.append(
                    PerformanceCachingFactEvidence(
                        evidence_id=make_cache_evidence_id(
                            kind=caching_kind.value, path=path, basis=basis
                        ),
                        kind=caching_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if concurrency_kind is not None:
                concurrency_facts.append(
                    PerformanceConcurrencyFactEvidence(
                        evidence_id=make_concurrency_evidence_id(
                            kind=concurrency_kind.value, path=path, basis=basis
                        ),
                        kind=concurrency_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if resource_kind is not None:
                resource_facts.append(
                    PerformanceResourceFactEvidence(
                        evidence_id=make_resource_evidence_id(
                            kind=resource_kind.value, path=path, basis=basis
                        ),
                        kind=resource_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if frontend_kind is not None:
                frontend_facts.append(
                    PerformanceFrontendFactEvidence(
                        evidence_id=make_frontend_evidence_id(
                            kind=frontend_kind.value, path=path, basis=basis
                        ),
                        kind=frontend_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if obs_kind is not None:
                obs_facts.append(
                    PerformanceObservabilityFactEvidence(
                        evidence_id=make_obs_evidence_id(
                            kind=obs_kind.value, path=path, basis=basis
                        ),
                        kind=obs_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )
            if config_kind is not None:
                config_facts.append(
                    PerformanceConfigurationFactEvidence(
                        evidence_id=make_config_evidence_id(
                            kind=config_kind.value, path=path, basis=basis
                        ),
                        kind=config_kind,
                        path=path,
                        confirmation_level=confirmation,
                        discovery_bases=unique_bases,
                        detail=detail,
                        line_hints=line_hints,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )

    file_candidates_t = _dedupe_by_id(file_candidates)
    data_facts_t = _dedupe_by_id(data_facts)
    blocking_facts_t = _dedupe_by_id(blocking_facts)
    caching_facts_t = _dedupe_by_id(caching_facts)
    concurrency_facts_t = _dedupe_by_id(concurrency_facts)
    resource_facts_t = _dedupe_by_id(resource_facts)
    frontend_facts_t = _dedupe_by_id(frontend_facts)
    obs_facts_t = _dedupe_by_id(obs_facts)
    config_facts_t = _dedupe_by_id(config_facts)
    diagnostics_t = _dedupe_by_id(diagnostics, id_attr="diagnostic_id")

    record_ids = tuple(
        sorted(
            {
                *(item.evidence_id for item in file_candidates_t),
                *(item.evidence_id for item in data_facts_t),
                *(item.evidence_id for item in blocking_facts_t),
                *(item.evidence_id for item in caching_facts_t),
                *(item.evidence_id for item in concurrency_facts_t),
                *(item.evidence_id for item in resource_facts_t),
                *(item.evidence_id for item in frontend_facts_t),
                *(item.evidence_id for item in obs_facts_t),
                *(item.evidence_id for item in config_facts_t),
            }
        )
    )
    fingerprint = evidence_bundle_fingerprint(
        repository_id=repository_id,
        record_ids=record_ids,
    )

    if not candidates and not relative_paths:
        status = RepositoryPerformanceParseStatus.INSUFFICIENT_EVIDENCE
    elif not candidates:
        status = RepositoryPerformanceParseStatus.SUCCEEDED
    elif malformed or unsupported or skipped:
        status = RepositoryPerformanceParseStatus.PARTIALLY_SUCCEEDED
    else:
        status = RepositoryPerformanceParseStatus.SUCCEEDED

    coverage = RepositoryPerformanceEvidenceCoverage(
        repository_files_considered=len(
            {
                normalize_relative_path(path)
                for path in relative_paths
                if normalize_relative_path(path)
            }
        ),
        candidate_files_discovered=len(candidates),
        candidate_files_inspected=inspected,
        structurally_confirmed_files=confirmed,
        unsupported_candidate_files=unsupported,
        malformed_files=malformed,
        skipped_files=skipped,
        data_access_facts=len(data_facts_t),
        blocking_operations_facts=len(blocking_facts_t),
        caching_facts=len(caching_facts_t),
        concurrency_async_facts=len(concurrency_facts_t),
        resource_management_facts=len(resource_facts_t),
        frontend_performance_facts=len(frontend_facts_t),
        observability_profiling_facts=len(obs_facts_t),
        configuration_controls_facts=len(config_facts_t),
        technologies_represented=tuple(sorted(technologies)),
        families_represented=tuple(sorted(families)),
    )

    return AggregatedRepositoryPerformanceEvidence(
        bundle_id=make_bundle_id(repository_id=repository_id, fingerprint=fingerprint),
        repository_id=repository_id,
        status=status,
        file_candidates=file_candidates_t,
        data_access_facts=data_facts_t,
        blocking_operations_facts=blocking_facts_t,
        caching_facts=caching_facts_t,
        concurrency_async_facts=concurrency_facts_t,
        resource_management_facts=resource_facts_t,
        frontend_performance_facts=frontend_facts_t,
        observability_profiling_facts=obs_facts_t,
        configuration_controls_facts=config_facts_t,
        coverage=coverage,
        diagnostics=diagnostics_t,
        limitations=standard_limitations(),
        evidence_fingerprint=fingerprint,
    )
