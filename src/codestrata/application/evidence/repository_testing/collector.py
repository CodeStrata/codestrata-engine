"""Collect aggregated repository-testing evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_testing.build_and_frameworks import (
    collect_build_and_framework_facts,
)
from codestrata.application.evidence.repository_testing.ci import collect_ci_facts
from codestrata.application.evidence.repository_testing.coverage_config import (
    collect_coverage_facts,
)
from codestrata.application.evidence.repository_testing.discovery import (
    DEFAULT_IGNORE_MARKERS,
    classification_for_path,
    discover_build_paths,
    discover_candidates,
    discover_ci_paths,
    discover_coverage_paths,
    discover_fixture_paths,
    normalize_relative_path,
)
from codestrata.application.evidence.repository_testing.fixtures import collect_fixture_facts
from codestrata.application.evidence.repository_testing.limitations import (
    standard_limitations,
)
from codestrata.application.evidence.repository_testing.markers import collect_marker_facts
from codestrata.application.evidence.repository_testing.structural import (
    inspect_structural_facts,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_testing.enums import (
    EvidenceConfirmationLevel,
    FrameworkEvidenceBasis,
    RepositoryTestingParseStatus,
    TestDiscoveryBasis,
)
from codestrata.domain.evidence.repository_testing.identifiers import (
    PROVIDER_ID,
    PROVIDER_VERSION,
    evidence_bundle_fingerprint,
    make_bundle_id,
    make_diagnostic_id,
    make_file_evidence_id,
    make_framework_evidence_id,
    make_type_evidence_id,
)
from codestrata.domain.evidence.repository_testing.models import (
    AggregatedRepositoryTestingEvidence,
    CiTestInvocationFactEvidence,
    FrameworkFactEvidence,
    MarkerFactEvidence,
    RepositoryTestingDiagnostic,
    RepositoryTestingEvidenceCoverage,
    StructuralTestFactEvidence,
    TestFileCandidateEvidence,
    TestTypeFactEvidence,
)


def _candidate_provenance(
    path: str, *, configuration_fingerprint: str
) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        source_analyzer="repository_testing_discovery",
        extraction_method="path_convention",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _diagnostic(*, code: str, message: str, path: str | None) -> RepositoryTestingDiagnostic:
    return RepositoryTestingDiagnostic(
        diagnostic_id=make_diagnostic_id(
            code=code, path=path or "", detail=message
        ),
        diagnostic_code=code,
        message=message,
        origin="orchestration",
        path=path,
    )


def collect_repository_testing_evidence(
    *,
    repository_id: str,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    load_errors: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    configuration_fingerprint: str = "",
) -> AggregatedRepositoryTestingEvidence:
    """Collect deterministic repository-testing evidence (no Findings)."""

    errors = dict(load_errors or {})
    texts = {
        normalize_relative_path(path): text for path, text in file_texts.items()
    }

    candidates = discover_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    build_paths = discover_build_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    ci_paths = discover_ci_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    fixture_paths = discover_fixture_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    coverage_paths = discover_coverage_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    diagnostics: list[RepositoryTestingDiagnostic] = []
    file_candidates: list[TestFileCandidateEvidence] = []
    structural_facts: list[StructuralTestFactEvidence] = []
    marker_facts: list[MarkerFactEvidence] = []
    test_type_facts: list[TestTypeFactEvidence] = []

    inspected = 0
    confirmed = 0
    supported_parsed = 0
    unsupported = 0
    malformed = 0
    skipped = 0
    roles_represented: set[str] = set()
    languages_represented: set[str] = set()

    for path, role, bases, language_hint in candidates:
        roles_represented.add(role.value)
        if language_hint:
            languages_represented.add(language_hint)

        size_bytes = None
        confirmation = EvidenceConfirmationLevel.DISCOVERED_CANDIDATE
        if path in errors:
            code = errors[path]
            if code == "file_too_large":
                skipped += 1
                message = "Candidate exceeded size limit; content not inspected."
            elif code == "truncated_parsing":
                # Still inspect truncated text when available.
                message = "Candidate text truncated during load."
            elif code == "unsupported_encoding":
                unsupported += 1
                skipped += 1
                message = "Candidate encoding unsupported; content not inspected."
            else:
                skipped += 1
                message = "Candidate could not be read; content not inspected."
            diagnostics.append(
                _diagnostic(code=code, message=message, path=path)
            )

        text = texts.get(path)
        if text is not None:
            size_bytes = len(text.encode("utf-8"))
            inspected += 1
            structural = inspect_structural_facts(
                path,
                text,
                configuration_fingerprint=configuration_fingerprint,
            )
            if structural is not None:
                structural_facts.append(structural)
                supported_parsed += 1
                if (
                    structural.confirmation_level
                    is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
                ):
                    confirmed += 1
                    confirmation = EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED
                else:
                    confirmation = EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED
            markers = collect_marker_facts(
                path,
                text,
                configuration_fingerprint=configuration_fingerprint,
            )
            marker_facts.extend(markers)
        elif path in errors and errors[path] not in {"truncated_parsing"}:
            pass
        elif path not in errors:
            # Path discovered but text not supplied — still a candidate.
            skipped += 1
            diagnostics.append(
                _diagnostic(
                    code="text_unavailable",
                    message="Candidate text unavailable for inspection.",
                    path=path,
                )
            )

        file_candidates.append(
            TestFileCandidateEvidence(
                evidence_id=make_file_evidence_id(path=path, role=role.value),
                path=path,
                role=role,
                confirmation_level=confirmation,
                discovery_bases=bases,
                classification=classification_for_path(path),
                language_hint=language_hint,
                size_bytes=size_bytes,
                provenance=_candidate_provenance(
                    path, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )
        test_type_facts.append(
            TestTypeFactEvidence(
                evidence_id=make_type_evidence_id(
                    test_type=role.value,
                    path=path,
                    basis=(
                        bases[0].value
                        if bases
                        else TestDiscoveryBasis.DIRECTORY_CONVENTION.value
                    ),
                ),
                test_type=role,
                path=path,
                discovery_bases=bases,
                detail=role.value,
                provenance=_candidate_provenance(
                    path, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )

    # Build / framework facts from manifests present in texts.
    framework_facts, build_facts = collect_build_and_framework_facts(
        {
            path: texts[path]
            for path, _ in build_paths
            if path in texts
        },
        configuration_fingerprint=configuration_fingerprint,
    )
    for path, _ in build_paths:
        if path in errors and path not in texts:
            diagnostics.append(
                _diagnostic(
                    code=errors[path],
                    message=f"Build manifest not parsed ({errors[path]}).",
                    path=path,
                )
            )

    # Structural framework observations.
    observed: list[FrameworkFactEvidence] = list(framework_facts)
    for structural in structural_facts:
        for hint in structural.framework_hints:
            observed.append(
                FrameworkFactEvidence(
                    evidence_id=make_framework_evidence_id(
                        framework=hint.value,
                        path=structural.path,
                        basis=FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED.value,
                    ),
                    framework=hint,
                    basis=FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED,
                    path=structural.path,
                    detail="structural_token",
                    provenance=_candidate_provenance(
                        structural.path,
                        configuration_fingerprint=configuration_fingerprint,
                    ),
                )
            )
    framework_by_id = {item.evidence_id: item for item in observed}
    framework_facts = tuple(
        sorted(framework_by_id.values(), key=lambda item: item.evidence_id)
    )

    ci_facts: list[CiTestInvocationFactEvidence] = []
    for path in ci_paths:
        if path in errors and path not in texts:
            diagnostics.append(
                _diagnostic(
                    code=errors[path],
                    message=f"CI workflow not parsed ({errors[path]}).",
                    path=path,
                )
            )
            continue
        text = texts.get(path)
        if text is None:
            continue
        ci_facts.extend(
            collect_ci_facts(
                path,
                text,
                configuration_fingerprint=configuration_fingerprint,
            )
        )

    size_by_path = {
        path: len(text.encode("utf-8")) for path, text in texts.items()
    }
    fixture_facts = collect_fixture_facts(
        fixture_paths,
        size_by_path=size_by_path,
        configuration_fingerprint=configuration_fingerprint,
    )
    coverage_fact_paths = sorted(
        {
            *(path for path, _ in coverage_paths),
            *(path for path, _ in build_paths),
        }
    )
    coverage_facts = collect_coverage_facts(
        coverage_fact_paths,
        file_texts=texts,
        configuration_fingerprint=configuration_fingerprint,
    )

    # Sort all fact tuples by evidence_id.
    file_candidates.sort(key=lambda item: item.evidence_id)
    structural_facts.sort(key=lambda item: item.evidence_id)
    test_type_facts.sort(key=lambda item: item.evidence_id)
    marker_facts_sorted = sorted(marker_facts, key=lambda item: item.evidence_id)
    build_facts_sorted = tuple(
        sorted(build_facts, key=lambda item: item.evidence_id)
    )
    ci_facts_sorted = tuple(sorted(ci_facts, key=lambda item: item.evidence_id))

    seen_diag: set[str] = set()
    unique_diagnostics: list[RepositoryTestingDiagnostic] = []
    for item in sorted(
        diagnostics,
        key=lambda d: (d.path or "", d.diagnostic_code, d.diagnostic_id),
    ):
        if item.diagnostic_id in seen_diag:
            continue
        seen_diag.add(item.diagnostic_id)
        unique_diagnostics.append(item)

    declared_frameworks = sum(
        1
        for item in framework_facts
        if item.basis is FrameworkEvidenceBasis.DECLARED
    )
    observed_frameworks = sum(
        1
        for item in framework_facts
        if item.basis is FrameworkEvidenceBasis.STRUCTURALLY_OBSERVED
    )
    coverage_configurations = sum(
        1
        for item in coverage_facts
        if item.fact_type.value.endswith("configuration")
        or "configuration" in item.fact_type.value
    )

    record_ids = tuple(
        sorted(
            {
                *(item.evidence_id for item in file_candidates),
                *(item.evidence_id for item in structural_facts),
                *(item.evidence_id for item in framework_facts),
                *(item.evidence_id for item in test_type_facts),
                *(item.evidence_id for item in build_facts_sorted),
                *(item.evidence_id for item in marker_facts_sorted),
                *(item.evidence_id for item in fixture_facts),
                *(item.evidence_id for item in coverage_facts),
                *(item.evidence_id for item in ci_facts_sorted),
            }
        )
    )
    fingerprint = evidence_bundle_fingerprint(
        repository_id=repository_id,
        record_ids=record_ids,
    )
    bundle_id = make_bundle_id(
        repository_id=repository_id, fingerprint=fingerprint
    )

    any_facts = bool(record_ids)
    status = RepositoryTestingParseStatus.SUCCEEDED
    if unique_diagnostics or malformed or skipped or unsupported:
        status = RepositoryTestingParseStatus.PARTIALLY_SUCCEEDED
    if (
        relative_paths
        and not any_facts
        and errors
        and not texts
    ):
        status = RepositoryTestingParseStatus.FAILED

    coverage = RepositoryTestingEvidenceCoverage(
        repository_files_considered=len(
            {normalize_relative_path(path) for path in relative_paths if path}
        ),
        candidate_test_files_discovered=len(candidates),
        candidate_files_inspected=inspected,
        structurally_confirmed_test_files=confirmed,
        supported_test_files_parsed=supported_parsed,
        unsupported_candidate_files=unsupported,
        malformed_files=malformed,
        skipped_files=skipped,
        build_manifests_inspected=sum(1 for path, _ in build_paths if path in texts),
        ci_files_inspected=sum(1 for path in ci_paths if path in texts),
        frameworks_declared=declared_frameworks,
        frameworks_structurally_observed=observed_frameworks,
        marker_facts=len(marker_facts_sorted),
        coverage_configurations=coverage_configurations,
        fixture_support_candidates=len(fixture_facts),
        source_roles_represented=tuple(sorted(roles_represented)),
        languages_represented=tuple(sorted(languages_represented)),
    )

    return AggregatedRepositoryTestingEvidence(
        bundle_id=bundle_id,
        repository_id=repository_id,
        status=status,
        file_candidates=tuple(file_candidates),
        structural_test_facts=tuple(structural_facts),
        framework_facts=framework_facts,
        test_type_facts=tuple(test_type_facts),
        build_configuration_facts=build_facts_sorted,
        marker_facts=tuple(marker_facts_sorted),
        fixture_facts=fixture_facts,
        coverage_facts=coverage_facts,
        ci_test_invocation_facts=ci_facts_sorted,
        coverage=coverage,
        diagnostics=tuple(unique_diagnostics),
        limitations=standard_limitations(),
        evidence_fingerprint=fingerprint,
    )


__all__ = [
    "collect_repository_testing_evidence",
    "discover_candidates",
]
