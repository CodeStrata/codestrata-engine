"""Collect aggregated repository-cloud evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_cloud.discovery import (
    DEFAULT_IGNORE_MARKERS,
    discover_cloud_candidates,
    normalize_relative_path,
)
from codestrata.application.evidence.repository_cloud.inspectors import (
    detect_managed_services,
    inspect_container_text,
    inspect_deployment_text,
    inspect_iac_text,
    inspect_orchestration_text,
    inspect_serverless_text,
)
from codestrata.application.evidence.repository_cloud.limitations import standard_limitations
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudDiscoveryBasis,
    CloudEvidenceFamily,
    CloudPlatformKind,
    EvidenceConfirmationLevel,
    RepositoryCloudParseStatus,
)
from codestrata.domain.evidence.repository_cloud.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    evidence_bundle_fingerprint,
    make_bundle_id,
    make_container_evidence_id,
    make_deployment_evidence_id,
    make_diagnostic_id,
    make_file_evidence_id,
    make_iac_evidence_id,
    make_orchestration_evidence_id,
    make_platform_evidence_id,
    make_serverless_evidence_id,
    make_service_evidence_id,
)
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
    CloudContainerFactEvidence,
    CloudDeploymentFactEvidence,
    CloudFileCandidateEvidence,
    CloudIaCFactEvidence,
    CloudManagedServiceFactEvidence,
    CloudOrchestrationFactEvidence,
    CloudPlatformFactEvidence,
    CloudServerlessFactEvidence,
    RepositoryCloudDiagnostic,
    RepositoryCloudEvidenceCoverage,
)


def _provenance(path: str, *, configuration_fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_cloud_discovery",
        extraction_method="path_convention",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _diagnostic(*, code: str, message: str, path: str | None) -> RepositoryCloudDiagnostic:
    return RepositoryCloudDiagnostic(
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


def collect_repository_cloud_evidence(
    *,
    repository_id: str,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    load_errors: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    configuration_fingerprint: str = "",
) -> AggregatedRepositoryCloudEvidence:
    """Collect deterministic repository-cloud evidence (no Findings)."""

    errors = dict(load_errors or {})
    texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
    candidates = discover_cloud_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    diagnostics: list[RepositoryCloudDiagnostic] = []
    file_candidates: list[CloudFileCandidateEvidence] = []
    platform_facts: list[CloudPlatformFactEvidence] = []
    container_facts: list[CloudContainerFactEvidence] = []
    orchestration_facts: list[CloudOrchestrationFactEvidence] = []
    iac_facts: list[CloudIaCFactEvidence] = []
    serverless_facts: list[CloudServerlessFactEvidence] = []
    managed_service_facts: list[CloudManagedServiceFactEvidence] = []
    deployment_facts: list[CloudDeploymentFactEvidence] = []

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
        platforms: tuple[CloudPlatformKind, ...] = ()

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
        hit = None
        if text is not None:
            inspected += 1
            if candidate.family is CloudEvidenceFamily.CONTAINER:
                hit = inspect_container_text(text, kind=candidate.container_kind)
            elif candidate.family is CloudEvidenceFamily.ORCHESTRATION:
                hit = inspect_orchestration_text(text, kind=candidate.orchestration_kind)
            elif candidate.family is CloudEvidenceFamily.IAC:
                hit = inspect_iac_text(text, kind=candidate.iac_kind)
            elif candidate.family is CloudEvidenceFamily.SERVERLESS:
                hit = inspect_serverless_text(text, kind=candidate.serverless_kind)
            elif candidate.family is CloudEvidenceFamily.DEPLOYMENT:
                hit = inspect_deployment_text(text, system=candidate.deployment_system)

            if hit is not None:
                confirmation = hit.confirmation_level
                bases.extend(hit.discovery_bases)
                detail = hit.detail
                line_hints = hit.line_hints
                platforms = hit.platforms
                if hit.container_kind is not None:
                    technologies.add(hit.container_kind.value)
                if hit.orchestration_kind is not None:
                    technologies.add(hit.orchestration_kind.value)
                if hit.iac_kind is not None:
                    technologies.add(hit.iac_kind.value)
                if hit.serverless_kind is not None:
                    technologies.add(hit.serverless_kind.value)
                if hit.deployment_system is not None:
                    technologies.add(hit.deployment_system.value)
                for platform in platforms:
                    technologies.add(platform.value)

            for service, _pattern, service_lines in detect_managed_services(text):
                technologies.add(service.value)
                families.add(CloudEvidenceFamily.MANAGED_SERVICE.value)
                managed_service_facts.append(
                    CloudManagedServiceFactEvidence(
                        evidence_id=make_service_evidence_id(
                            service=service.value,
                            path=path,
                            basis="content_marker",
                        ),
                        service=service,
                        path=path,
                        confirmation_level=(EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED),
                        discovery_bases=(CloudDiscoveryBasis.CONTENT_MARKER,),
                        detail=f"managed_service:{service.value}",
                        line_hints=service_lines,
                        provenance=_provenance(
                            path, configuration_fingerprint=configuration_fingerprint
                        ),
                    )
                )

            if confirmation is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED:
                confirmed += 1

        unique_bases = tuple(dict.fromkeys(bases))
        file_candidates.append(
            CloudFileCandidateEvidence(
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

        container_kind = (
            hit.container_kind
            if hit is not None and hit.container_kind
            else candidate.container_kind
        )
        orchestration_kind = (
            hit.orchestration_kind
            if hit is not None and hit.orchestration_kind
            else candidate.orchestration_kind
        )
        iac_kind = hit.iac_kind if hit is not None and hit.iac_kind else candidate.iac_kind
        serverless_kind = (
            hit.serverless_kind
            if hit is not None and hit.serverless_kind
            else candidate.serverless_kind
        )
        deployment_system = (
            hit.deployment_system
            if hit is not None and hit.deployment_system
            else candidate.deployment_system
        )

        if container_kind is not None:
            container_facts.append(
                CloudContainerFactEvidence(
                    evidence_id=make_container_evidence_id(
                        kind=container_kind.value,
                        path=path,
                        basis=unique_bases[0].value if unique_bases else "path",
                    ),
                    kind=container_kind,
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
        if orchestration_kind is not None:
            orchestration_facts.append(
                CloudOrchestrationFactEvidence(
                    evidence_id=make_orchestration_evidence_id(
                        kind=orchestration_kind.value,
                        path=path,
                        basis=unique_bases[0].value if unique_bases else "path",
                    ),
                    kind=orchestration_kind,
                    path=path,
                    confirmation_level=confirmation,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path,
                        configuration_fingerprint=configuration_fingerprint,
                    ),
                )
            )
        if iac_kind is not None:
            iac_facts.append(
                CloudIaCFactEvidence(
                    evidence_id=make_iac_evidence_id(
                        kind=iac_kind.value,
                        path=path,
                        basis=unique_bases[0].value if unique_bases else "path",
                    ),
                    kind=iac_kind,
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
        if serverless_kind is not None:
            serverless_facts.append(
                CloudServerlessFactEvidence(
                    evidence_id=make_serverless_evidence_id(
                        kind=serverless_kind.value,
                        path=path,
                        basis=unique_bases[0].value if unique_bases else "path",
                    ),
                    kind=serverless_kind,
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
        if deployment_system is not None:
            deployment_facts.append(
                CloudDeploymentFactEvidence(
                    evidence_id=make_deployment_evidence_id(
                        system=deployment_system.value,
                        path=path,
                        basis=unique_bases[0].value if unique_bases else "path",
                    ),
                    system=deployment_system,
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

        for platform in platforms:
            if platform is CloudPlatformKind.UNKNOWN:
                continue
            platform_facts.append(
                CloudPlatformFactEvidence(
                    evidence_id=make_platform_evidence_id(
                        platform=platform.value,
                        path=path,
                        basis="content_marker",
                    ),
                    platform=platform,
                    path=path,
                    confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
                    discovery_bases=unique_bases,
                    detail=detail,
                    line_hints=line_hints,
                    provenance=_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )

    file_candidates_t = _dedupe_by_id(file_candidates)
    platform_facts_t = _dedupe_by_id(platform_facts)
    container_facts_t = _dedupe_by_id(container_facts)
    orchestration_facts_t = _dedupe_by_id(orchestration_facts)
    iac_facts_t = _dedupe_by_id(iac_facts)
    serverless_facts_t = _dedupe_by_id(serverless_facts)
    managed_service_facts_t = _dedupe_by_id(managed_service_facts)
    deployment_facts_t = _dedupe_by_id(deployment_facts)
    diagnostics_t = _dedupe_by_id(diagnostics, id_attr="diagnostic_id")

    record_ids = tuple(
        sorted(
            {
                *(item.evidence_id for item in file_candidates_t),
                *(item.evidence_id for item in platform_facts_t),
                *(item.evidence_id for item in container_facts_t),
                *(item.evidence_id for item in orchestration_facts_t),
                *(item.evidence_id for item in iac_facts_t),
                *(item.evidence_id for item in serverless_facts_t),
                *(item.evidence_id for item in managed_service_facts_t),
                *(item.evidence_id for item in deployment_facts_t),
            }
        )
    )
    fingerprint = evidence_bundle_fingerprint(
        repository_id=repository_id,
        record_ids=record_ids,
    )

    if not candidates and not relative_paths:
        status = RepositoryCloudParseStatus.INSUFFICIENT_EVIDENCE
    elif not candidates:
        status = RepositoryCloudParseStatus.SUCCEEDED
    elif malformed or unsupported or skipped:
        status = RepositoryCloudParseStatus.PARTIALLY_SUCCEEDED
    else:
        status = RepositoryCloudParseStatus.SUCCEEDED

    coverage = RepositoryCloudEvidenceCoverage(
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
        platform_facts=len(platform_facts_t),
        container_facts=len(container_facts_t),
        orchestration_facts=len(orchestration_facts_t),
        iac_facts=len(iac_facts_t),
        serverless_facts=len(serverless_facts_t),
        managed_service_facts=len(managed_service_facts_t),
        deployment_facts=len(deployment_facts_t),
        technologies_represented=tuple(sorted(technologies)),
        families_represented=tuple(sorted(families)),
    )

    return AggregatedRepositoryCloudEvidence(
        bundle_id=make_bundle_id(repository_id=repository_id, fingerprint=fingerprint),
        repository_id=repository_id,
        status=status,
        file_candidates=file_candidates_t,
        platform_facts=platform_facts_t,
        container_facts=container_facts_t,
        orchestration_facts=orchestration_facts_t,
        iac_facts=iac_facts_t,
        serverless_facts=serverless_facts_t,
        managed_service_facts=managed_service_facts_t,
        deployment_facts=deployment_facts_t,
        coverage=coverage,
        diagnostics=diagnostics_t,
        limitations=standard_limitations(),
        evidence_fingerprint=fingerprint,
    )
