"""Collect repository-sensitive artifact and configuration evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.repository_sensitive.config_parsers import (
    parse_configuration,
)
from codestrata.application.evidence.repository_sensitive.discovery import (
    DEFAULT_IGNORE_MARKERS,
    classification_for_path,
    discover_candidates,
    discover_configuration_paths,
    is_binary_extension,
)
from codestrata.application.evidence.repository_sensitive.limitations import (
    standard_limitations,
)
from codestrata.application.evidence.repository_sensitive.signatures import (
    classify_text_signatures,
)
from codestrata.domain.evidence.language.capabilities import (
    EvidenceOrigin,
    SourceClassification,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_sensitive.enums import (
    ContentClassification,
    DiscoveryBasis,
    InspectionStatus,
    PlaceholderStatus,
    RepositorySensitiveParseStatus,
    SensitiveArtifactKind,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import (
    ARTIFACT_PROVIDER_ID,
    ARTIFACT_PROVIDER_VERSION,
    CONFIGURATION_PROVIDER_ID,
    CONFIGURATION_PROVIDER_VERSION,
    evidence_bundle_fingerprint,
    fingerprint_bytes,
    fingerprint_value,
    make_artifact_evidence_id,
    make_configuration_evidence_id,
    make_diagnostic_id,
)
from codestrata.domain.evidence.repository_sensitive.models import (
    AggregatedRepositorySensitiveEvidence,
    ConfigurationFactEvidence,
    RepositorySensitiveDiagnostic,
    RepositorySensitiveEvidenceCoverage,
    SensitiveArtifactEvidence,
)


def _artifact_provenance(
    path: str, *, configuration_fingerprint: str
) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=ARTIFACT_PROVIDER_ID,
        provider_version=ARTIFACT_PROVIDER_VERSION,
        source_analyzer="repository_sensitive_artifact_collector",
        extraction_method="content_signature",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _config_provenance(
    path: str, *, configuration_fingerprint: str
) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=CONFIGURATION_PROVIDER_ID,
        provider_version=CONFIGURATION_PROVIDER_VERSION,
        source_analyzer="repository_sensitive_configuration_collector",
        extraction_method="structured_parse",
        origin=EvidenceOrigin.SOURCE_PARSE,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )


def _refine_kind(
    kind: SensitiveArtifactKind,
    classifications: tuple[ContentClassification, ...],
) -> SensitiveArtifactKind:
    if ContentClassification.PRIVATE_KEY_MATERIAL in classifications:
        if kind is SensitiveArtifactKind.SSH_PRIVATE_KEY:
            return SensitiveArtifactKind.SSH_PRIVATE_KEY
        return SensitiveArtifactKind.PRIVATE_KEY
    if (
        ContentClassification.PUBLIC_CERTIFICATE_MATERIAL in classifications
        and ContentClassification.PRIVATE_KEY_MATERIAL not in classifications
    ):
        return SensitiveArtifactKind.PUBLIC_CERTIFICATE
    return kind


def _diagnostic(
    *,
    code: str,
    message: str,
    path: str | None,
    classification: SourceClassification,
) -> RepositorySensitiveDiagnostic:
    return RepositorySensitiveDiagnostic(
        diagnostic_id=make_diagnostic_id(
            code=code, path=path or "", detail=message
        ),
        diagnostic_code=code,
        message=message,
        path=path,
        classification=classification,
    )


def collect_repository_sensitive_evidence(
    *,
    repository_id: str,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    file_binaries: Mapping[str, bytes] | None = None,
    load_errors: Mapping[str, str] | None = None,
    ignore_path_markers: Sequence[str] = DEFAULT_IGNORE_MARKERS,
    max_files: int = 500,
    configuration_fingerprint: str = "",
) -> AggregatedRepositorySensitiveEvidence:
    """Collect deterministic repository-sensitive evidence (no Findings)."""

    binaries = file_binaries or {}
    errors = dict(load_errors or {})
    candidates = discover_candidates(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    config_paths = discover_configuration_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )

    artifacts: list[SensitiveArtifactEvidence] = []
    configuration_facts: list[ConfigurationFactEvidence] = []
    diagnostics: list[RepositorySensitiveDiagnostic] = []

    files_inspected = 0
    metadata_only = 0
    structured_parsed = 0
    malformed = 0
    unsupported_binaries = 0
    skipped = 0
    signatures_evaluated = 0
    formats: set[str] = set()

    for path, kind, bases in candidates:
        classification = classification_for_path(path)
        if path in errors:
            code = errors[path]
            if code == "file_too_large":
                status = InspectionStatus.SKIPPED_SIZE_LIMIT
                skipped += 1
                message = "Candidate exceeded size limit; content not inspected."
            elif code == "unsupported_encoding":
                status = InspectionStatus.FAILED
                skipped += 1
                message = "Candidate encoding unsupported; content not inspected."
            else:
                status = InspectionStatus.FAILED
                skipped += 1
                message = "Candidate could not be read; content not inspected."
            diagnostics.append(
                _diagnostic(
                    code=code,
                    message=message,
                    path=path,
                    classification=classification,
                )
            )
            artifacts.append(
                SensitiveArtifactEvidence(
                    evidence_id=make_artifact_evidence_id(
                        path=path, kind=kind.value
                    ),
                    path=path,
                    kind=kind,
                    discovery_bases=bases,
                    inspection_status=status,
                    content_classifications=(ContentClassification.UNKNOWN,),
                    classification=classification,
                    size_bytes=None,
                    content_fingerprint=None,
                    provenance=_artifact_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                    diagnostics=(code,),
                )
            )
            continue

        if is_binary_extension(path) or path in binaries:
            raw = binaries.get(path, b"")
            fp = fingerprint_bytes(raw) if raw else None
            unsupported_binaries += 1
            metadata_only += 1
            diagnostics.append(
                _diagnostic(
                    code="binary_artifact_not_inspected",
                    message=(
                        "Binary keystore/truststore inspected as metadata only; "
                        "no decryption attempted."
                    ),
                    path=path,
                    classification=classification,
                )
            )
            artifacts.append(
                SensitiveArtifactEvidence(
                    evidence_id=make_artifact_evidence_id(
                        path=path, kind=kind.value
                    ),
                    path=path,
                    kind=kind,
                    discovery_bases=bases,
                    inspection_status=InspectionStatus.UNSUPPORTED_BINARY,
                    content_classifications=(ContentClassification.UNKNOWN,),
                    classification=classification,
                    size_bytes=len(raw) if raw else None,
                    content_fingerprint=fp,
                    provenance=_artifact_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                    metadata={"inspection": "metadata_only"},
                    diagnostics=("binary_artifact_not_inspected",),
                )
            )
            continue

        text = file_texts.get(path)
        if text is None:
            skipped += 1
            diagnostics.append(
                _diagnostic(
                    code="unreadable_file",
                    message="Candidate text unavailable for inspection.",
                    path=path,
                    classification=classification,
                )
            )
            artifacts.append(
                SensitiveArtifactEvidence(
                    evidence_id=make_artifact_evidence_id(
                        path=path, kind=kind.value
                    ),
                    path=path,
                    kind=kind,
                    discovery_bases=bases,
                    inspection_status=InspectionStatus.FAILED,
                    content_classifications=(ContentClassification.UNKNOWN,),
                    classification=classification,
                    provenance=_artifact_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                    diagnostics=("unreadable_file",),
                )
            )
            continue

        files_inspected += 1
        signatures_evaluated += 1
        content_classes = classify_text_signatures(text)
        refined = _refine_kind(kind, content_classes)
        discovery = list(bases)
        if content_classes != (
            ContentClassification.NO_SUPPORTED_SENSITIVE_SIGNATURE,
        ):
            discovery.append(DiscoveryBasis.CONTENT_SIGNATURE)
        # Filename alone does not imply sensitive content.
        artifacts.append(
            SensitiveArtifactEvidence(
                evidence_id=make_artifact_evidence_id(
                    path=path, kind=refined.value
                ),
                path=path,
                kind=refined,
                discovery_bases=tuple(dict.fromkeys(discovery)),
                inspection_status=InspectionStatus.INSPECTED,
                content_classifications=content_classes,
                classification=classification,
                size_bytes=len(text.encode("utf-8")),
                content_fingerprint=fingerprint_value(text),
                provenance=_artifact_provenance(
                    path, configuration_fingerprint=configuration_fingerprint
                ),
            )
        )

    for path in config_paths:
        classification = classification_for_path(path)
        if path in errors and path not in file_texts:
            code = errors[path]
            if code == "file_too_large":
                skipped += 1
            elif code in {"unsupported_encoding", "unreadable_file"}:
                skipped += 1
            diagnostics.append(
                _diagnostic(
                    code=code,
                    message=f"Configuration candidate not parsed ({code}).",
                    path=path,
                    classification=classification,
                )
            )
            continue

        text = file_texts.get(path)
        if text is None:
            continue

        fmt, parsed_facts, parse_diags = parse_configuration(path, text)
        formats.add(fmt.value)
        if parse_diags:
            hard_failure = not parsed_facts
            if hard_failure:
                malformed += 1
            for detail in parse_diags:
                code = detail.split(":", 1)[0]
                diagnostics.append(
                    _diagnostic(
                        code=code,
                        message=(
                            "Structured configuration could not be fully parsed; "
                            "no raw values are retained."
                        ),
                        path=path,
                        classification=classification,
                    )
                )
            if not parsed_facts:
                continue

        if parsed_facts:
            structured_parsed += 1
            files_inspected += 1

        for fact in parsed_facts:
            section = fact.get("section")
            section_text = str(section) if section else ""
            line = fact.get("line_start")
            line_text = str(line) if line is not None else ""
            normalized_key = str(fact["normalized_key"])
            configuration_facts.append(
                ConfigurationFactEvidence(
                    evidence_id=make_configuration_evidence_id(
                        path=path,
                        normalized_key=normalized_key,
                        section=section_text,
                        line=line_text,
                    ),
                    path=path,
                    classification=classification,
                    format=fmt,
                    normalized_key=normalized_key,
                    key_family=fact["key_family"],  # type: ignore[arg-type]
                    redacted_preview=str(fact["redacted_preview"]),
                    value_fingerprint=(
                        str(fact["value_fingerprint"])
                        if fact.get("value_fingerprint")
                        else None
                    ),
                    value_length=int(str(fact["value_length"])),
                    value_kind=fact["value_kind"],  # type: ignore[arg-type]
                    placeholder_status=fact["placeholder_status"],  # type: ignore[arg-type]
                    placeholder_kind=(
                        str(fact["placeholder_kind"])
                        if fact.get("placeholder_kind")
                        else None
                    ),
                    is_empty=bool(fact["is_empty"]),
                    literal_boolean=(
                        bool(fact["literal_boolean"])
                        if fact.get("literal_boolean") is not None
                        else None
                    ),
                    is_wildcard_origin=bool(fact.get("is_wildcard_origin")),
                    section=section_text or None,
                    profile=section_text or None,
                    line_start=int(line) if isinstance(line, int) else None,
                    parse_status=RepositorySensitiveParseStatus.SUCCEEDED,
                    provenance=_config_provenance(
                        path, configuration_fingerprint=configuration_fingerprint
                    ),
                )
            )

    artifacts.sort(key=lambda item: (item.path, item.evidence_id))
    configuration_facts.sort(
        key=lambda item: (
            item.path,
            item.normalized_key,
            item.section or "",
            item.line_start or 0,
            item.evidence_id,
        )
    )
    # Deduplicate diagnostics by id while preserving order.
    seen_diag: set[str] = set()
    unique_diagnostics: list[RepositorySensitiveDiagnostic] = []
    for item in sorted(
        diagnostics, key=lambda d: (d.path or "", d.diagnostic_code, d.diagnostic_id)
    ):
        if item.diagnostic_id in seen_diag:
            continue
        seen_diag.add(item.diagnostic_id)
        unique_diagnostics.append(item)

    placeholder_facts = sum(
        1
        for item in configuration_facts
        if item.placeholder_status
        in {
            PlaceholderStatus.EMPTY,
            PlaceholderStatus.PLACEHOLDER_LITERAL,
            PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
        }
        or item.is_empty
    )

    production = sum(
        1
        for item in artifacts
        if item.classification is SourceClassification.SOURCE
    )
    test_count = sum(
        1 for item in artifacts if item.classification is SourceClassification.TEST
    )
    unknown = sum(
        1
        for item in artifacts
        if item.classification is SourceClassification.UNKNOWN
    )

    parse_status = RepositorySensitiveParseStatus.SUCCEEDED
    if malformed or skipped or unsupported_binaries:
        parse_status = RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED
    if not artifacts and not configuration_facts and unique_diagnostics:
        # Still succeeded with empty evidence if only load issues on candidates.
        parse_status = RepositorySensitiveParseStatus.PARTIALLY_SUCCEEDED

    fingerprint = evidence_bundle_fingerprint(
        repository_id=repository_id,
        artifact_ids=tuple(item.evidence_id for item in artifacts),
        configuration_ids=tuple(item.evidence_id for item in configuration_facts),
    )

    coverage = RepositorySensitiveEvidenceCoverage(
        candidate_files_discovered=len(candidates),
        files_inspected=files_inspected,
        metadata_only_files=metadata_only,
        structured_files_parsed=structured_parsed,
        malformed_files=malformed,
        unsupported_binaries=unsupported_binaries,
        skipped_files=skipped,
        content_signatures_evaluated=signatures_evaluated,
        configuration_facts_collected=len(configuration_facts),
        placeholder_facts=placeholder_facts,
        production_artifacts=production,
        test_artifacts=test_count,
        unknown_artifacts=unknown,
        formats_represented=tuple(sorted(formats)),
    )

    return AggregatedRepositorySensitiveEvidence(
        repository_id=repository_id,
        status=parse_status,
        artifacts=tuple(artifacts),
        configuration_facts=tuple(configuration_facts),
        coverage=coverage,
        diagnostics=tuple(unique_diagnostics),
        limitations=standard_limitations(),
        evidence_fingerprint=fingerprint,
    )


# Re-export helpers used by service/tests.
__all__ = [
    "collect_repository_sensitive_evidence",
    "discover_candidates",
]
