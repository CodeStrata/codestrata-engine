"""Composer composer.json Dependency Evidence collector."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.dependency.paths import (
    classification_for_path,
    classify_manifest_basename,
    select_manifest_paths,
    texts_for_paths,
)
from codestrata.domain.evidence.dependency.enums import (
    DependencyDeclarationKind,
    DependencyEcosystem,
    DependencyEvidenceAvailability,
    DependencyManifestType,
    DependencyParseStatus,
    DependencyVersionResolutionStatus,
)
from codestrata.domain.evidence.dependency.identifiers import (
    COMPOSER_PROVIDER_ID,
    COMPOSER_PROVIDER_VERSION,
    make_declaration_evidence_id,
    make_manifest_evidence_id,
)
from codestrata.domain.evidence.dependency.models import (
    DependencyDeclarationEvidence,
    DependencyEvidenceBundle,
    DependencyEvidenceCoverage,
    DependencyManifestEvidence,
    DependencySourceLocation,
)
from codestrata.domain.evidence.language.capabilities import EvidenceOrigin
from codestrata.domain.evidence.language.provenance import EvidenceProvenance

_PLATFORM_PACKAGES = frozenset({"php", "hhvm", "composer-plugin-api"})


def _provenance(path: str, fingerprint: str, method: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=COMPOSER_PROVIDER_ID,
        provider_version=COMPOSER_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method=method,
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        configuration_fingerprint=fingerprint,
        transformation_chain=("composer",),
    )


def parse_composer_json_text(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> tuple[DependencyManifestEvidence, tuple[DependencyDeclarationEvidence, ...]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=COMPOSER_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.COMPOSER,
            manifest_type=DependencyManifestType.COMPOSER_JSON,
            parse_status=DependencyParseStatus.FAILED,
            classification=classification_for_path(path),
            diagnostics=(f"composer_parse_error:{error}",),
            provenance=_provenance(path, configuration_fingerprint, "json_parse"),
        )
        return manifest, ()

    if not isinstance(data, dict):
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=COMPOSER_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.COMPOSER,
            manifest_type=DependencyManifestType.COMPOSER_JSON,
            parse_status=DependencyParseStatus.FAILED,
            classification=classification_for_path(path),
            diagnostics=("composer_not_object",),
            provenance=_provenance(path, configuration_fingerprint, "json_parse"),
        )
        return manifest, ()

    declarations: list[DependencyDeclarationEvidence] = []
    unsupported: list[str] = []
    sections = (
        ("require", DependencyDeclarationKind.RUNTIME),
        ("require-dev", DependencyDeclarationKind.DEVELOPMENT),
    )
    for section_name, kind in sections:
        section = data.get(section_name)
        if section is None:
            continue
        if not isinstance(section, dict):
            unsupported.append(f"{path}:{section_name}:non_object")
            continue
        for name, version_value in sorted(section.items()):
            if not isinstance(name, str) or not name.strip():
                unsupported.append(f"{path}:{section_name}:invalid_name")
                continue
            package_name = name.strip()
            lower = package_name.lower()
            if lower in _PLATFORM_PACKAGES or lower.startswith(("ext-", "lib-")):
                continue
            raw_version = version_value if isinstance(version_value, str) else None
            if raw_version is None and version_value is not None:
                unsupported.append(f"{path}:{section_name}:{package_name}:non_string_version")
            declarations.append(
                DependencyDeclarationEvidence(
                    evidence_id=make_declaration_evidence_id(
                        provider_id=COMPOSER_PROVIDER_ID,
                        path=path,
                        identity=package_name.lower(),
                        kind=kind.value,
                        raw_version=raw_version or "",
                        profile="",
                        line="0",
                    ),
                    ecosystem=DependencyEcosystem.COMPOSER,
                    manifest_type=DependencyManifestType.COMPOSER_JSON,
                    declaration_kind=kind,
                    normalized_identity=package_name.lower(),
                    original_identity=package_name,
                    raw_version=raw_version,
                    resolved_version_local=raw_version,
                    version_availability=(
                        DependencyEvidenceAvailability.AVAILABLE
                        if raw_version
                        else DependencyEvidenceAvailability.UNAVAILABLE
                    ),
                    version_resolution_status=(
                        DependencyVersionResolutionStatus.RESOLVED
                        if raw_version
                        else DependencyVersionResolutionStatus.NOT_APPLICABLE
                    ),
                    extras=(),
                    environment_marker=None,
                    group_name=section_name,
                    is_editable=False,
                    is_local_path=bool(raw_version and raw_version.startswith("path:")),
                    source=DependencySourceLocation(
                        path=path,
                        line_start=None,
                        line_end=None,
                        snippet=f"{package_name}:{raw_version or ''}"[:200],
                    ),
                    classification=classification_for_path(path),
                    provenance=_provenance(
                        path, configuration_fingerprint, "composer_manifest_parse"
                    ),
                )
            )

    status = DependencyParseStatus.SUCCEEDED
    if unsupported and declarations:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    elif unsupported and not declarations:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED

    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=COMPOSER_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.COMPOSER,
        manifest_type=DependencyManifestType.COMPOSER_JSON,
        parse_status=status,
        classification=classification_for_path(path),
        declaration_count=len(declarations),
        unsupported_constructs=tuple(sorted(unsupported)),
        diagnostics=(),
        provenance=_provenance(path, configuration_fingerprint, "json_parse"),
    )
    return manifest, tuple(declarations)


def collect_composer_dependency_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str],
    max_files: int = 500,
    max_file_chars: int = 500_000,
    configuration_fingerprint: str = "",
) -> DependencyEvidenceBundle:
    paths, excluded = select_manifest_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
        ecosystems=(DependencyEcosystem.COMPOSER,),
    )
    texts = texts_for_paths(paths, file_texts)
    manifests: list[DependencyManifestEvidence] = []
    declarations: list[DependencyDeclarationEvidence] = []
    diagnostics: list[str] = []
    for path in paths:
        classified = classify_manifest_basename(path)
        if classified is None:
            continue
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"composer_text_missing:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"composer_truncated:{path}")
        manifest, decls = parse_composer_json_text(
            path=path,
            text=text,
            configuration_fingerprint=configuration_fingerprint,
        )
        manifests.append(manifest)
        declarations.extend(decls)

    manifests_t = tuple(sorted(manifests, key=lambda item: item.path))
    declarations_t = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.source.path,
                item.source.line_start or 0,
                item.normalized_identity,
                item.evidence_id,
            ),
        )
    )
    parsed = sum(
        1 for item in manifests_t if item.parse_status is DependencyParseStatus.SUCCEEDED
    )
    partial = sum(
        1
        for item in manifests_t
        if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
    )
    failed = sum(1 for item in manifests_t if item.parse_status is DependencyParseStatus.FAILED)
    unsupported_count = sum(len(item.unsupported_constructs) for item in manifests_t)
    if failed and not parsed and not partial:
        status = DependencyParseStatus.FAILED
    elif manifests_t and (partial or failed or unsupported_count):
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    elif manifests_t:
        status = DependencyParseStatus.SUCCEEDED
    else:
        status = DependencyParseStatus.NOT_APPLICABLE

    coverage = DependencyEvidenceCoverage(
        manifests_discovered=len(paths) + excluded,
        manifests_supported=len(paths),
        manifests_parsed=parsed,
        manifests_partially_parsed=partial,
        manifests_failed=failed,
        manifests_excluded=excluded,
        declarations_collected=len(declarations_t),
        unsupported_construct_count=unsupported_count,
        unresolved_expression_count=0,
    )
    return DependencyEvidenceBundle(
        provider_id=COMPOSER_PROVIDER_ID,
        provider_version=COMPOSER_PROVIDER_VERSION,
        ecosystem=DependencyEcosystem.COMPOSER,
        status=status,
        manifests=manifests_t,
        declarations=declarations_t,
        coverage=coverage,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
