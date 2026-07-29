"""NuGet Dependency Evidence collector (.csproj, packages.config, Directory.Packages.props)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from codestrata.application.evidence.dependency.paths import (
    classification_for_path,
    classify_manifest_basename,
    is_ignored_path,
    normalize_relative_path,
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
    NUGET_PROVIDER_ID,
    NUGET_PROVIDER_VERSION,
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

_PACKAGE_REFERENCE_ATTR = re.compile(
    r"""<PackageReference\b(?P<attrs>[^>]*)/?>""",
    re.IGNORECASE,
)
_ATTR = re.compile(
    r"""(?P<key>Include|Version|PrivateAssets)\s*=\s*["'](?P<value>[^"']*)["']""",
    re.IGNORECASE,
)
_PACKAGE_REFERENCE_VERSION_CHILD = re.compile(
    r"""<PackageReference\b[^>]*\bInclude\s*=\s*["'](?P<name>[^"']+)["'][^>]*>"""
    r"""\s*<Version>\s*(?P<version>[^<]+)\s*</Version>""",
    re.IGNORECASE | re.DOTALL,
)
_PACKAGE_VERSION_CPM = re.compile(
    r"""<PackageVersion\b(?P<attrs>[^>]*)/?>""",
    re.IGNORECASE,
)
_PACKAGES_CONFIG = re.compile(
    r"""<package\b[^>]*\bid\s*=\s*["'](?P<name>[^"']+)["']"""
    r"""[^>]*\bversion\s*=\s*["'](?P<version>[^"']+)["']""",
    re.IGNORECASE,
)


def _provenance(path: str, fingerprint: str, method: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=NUGET_PROVIDER_ID,
        provider_version=NUGET_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method=method,
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        configuration_fingerprint=fingerprint,
        transformation_chain=("nuget",),
    )


def _attrs(blob: str) -> dict[str, str]:
    return {match.group("key").lower(): match.group("value") for match in _ATTR.finditer(blob)}


def select_nuget_manifest_paths(
    relative_paths: Sequence[str],
    *,
    ignore_markers: Sequence[str],
    max_files: int = 500,
) -> tuple[tuple[str, ...], int]:
    eligible: list[str] = []
    excluded = 0
    for raw in relative_paths:
        path = normalize_relative_path(raw)
        if not path:
            continue
        classified = classify_manifest_basename(path)
        if classified is None or classified[0] is not DependencyEcosystem.NUGET:
            continue
        if is_ignored_path(path, ignore_markers=ignore_markers):
            excluded += 1
            continue
        # Prefer declaration manifests over lockfiles for evidence collection.
        name = PurePosixPath(path).name.lower()
        if name == "packages.lock.json":
            continue
        eligible.append(path)
    ordered = tuple(sorted(set(eligible)))
    if len(ordered) > max_files:
        return ordered[:max_files], excluded + (len(ordered) - max_files)
    return ordered, excluded


def parse_nuget_manifest_text(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> tuple[DependencyManifestEvidence, tuple[DependencyDeclarationEvidence, ...]]:
    classified = classify_manifest_basename(path)
    if classified is None:
        manifest_type = DependencyManifestType.UNKNOWN
    else:
        manifest_type = classified[1]

    declarations: list[DependencyDeclarationEvidence] = []
    unsupported: list[str] = []
    name = PurePosixPath(path).name.lower()

    if name.endswith(".csproj") or name.endswith(".fsproj") or name.endswith(".vbproj"):
        seen: set[str] = set()
        for match in _PACKAGE_REFERENCE_ATTR.finditer(text):
            attrs = _attrs(match.group("attrs"))
            package_name = attrs.get("include", "").strip()
            if not package_name:
                unsupported.append(f"{path}:PackageReference:missing_include")
                continue
            version = attrs.get("version", "").strip() or None
            private = attrs.get("privateassets", "").lower()
            kind = (
                DependencyDeclarationKind.DEVELOPMENT
                if "all" in private
                else DependencyDeclarationKind.RUNTIME
            )
            key = package_name.lower()
            if key in seen and not version:
                continue
            seen.add(key)
            declarations.append(
                _declaration(
                    path=path,
                    package_name=package_name,
                    raw_version=version,
                    kind=kind,
                    manifest_type=manifest_type,
                    group_name="PackageReference",
                    fingerprint=configuration_fingerprint,
                    method="csproj_package_reference",
                )
            )
        for match in _PACKAGE_REFERENCE_VERSION_CHILD.finditer(text):
            package_name = match.group("name").strip()
            version = match.group("version").strip()
            key = package_name.lower()
            # Prefer explicit Version child over empty attribute.
            declarations = [
                item
                for item in declarations
                if item.normalized_identity != key or item.raw_version
            ]
            declarations.append(
                _declaration(
                    path=path,
                    package_name=package_name,
                    raw_version=version,
                    kind=DependencyDeclarationKind.RUNTIME,
                    manifest_type=manifest_type,
                    group_name="PackageReference",
                    fingerprint=configuration_fingerprint,
                    method="csproj_package_reference",
                )
            )
    elif name == "packages.config":
        for match in _PACKAGES_CONFIG.finditer(text):
            declarations.append(
                _declaration(
                    path=path,
                    package_name=match.group("name").strip(),
                    raw_version=match.group("version").strip(),
                    kind=DependencyDeclarationKind.RUNTIME,
                    manifest_type=manifest_type,
                    group_name="packages.config",
                    fingerprint=configuration_fingerprint,
                    method="packages_config_parse",
                )
            )
    elif name == "directory.packages.props":
        for match in _PACKAGE_VERSION_CPM.finditer(text):
            attrs = _attrs(match.group("attrs"))
            package_name = attrs.get("include", "").strip()
            version = attrs.get("version", "").strip() or None
            if not package_name:
                unsupported.append(f"{path}:PackageVersion:missing_include")
                continue
            declarations.append(
                _declaration(
                    path=path,
                    package_name=package_name,
                    raw_version=version,
                    kind=DependencyDeclarationKind.DEPENDENCY_MANAGEMENT,
                    manifest_type=manifest_type,
                    group_name="PackageVersion",
                    fingerprint=configuration_fingerprint,
                    method="directory_packages_props",
                    is_dependency_management=True,
                )
            )
    else:
        unsupported.append(f"{path}:unsupported_nuget_manifest")

    status = DependencyParseStatus.SUCCEEDED
    if unsupported and declarations:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    elif unsupported and not declarations:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED

    # Deduplicate by identity+kind+version keeping first.
    unique: dict[tuple[str, str, str], DependencyDeclarationEvidence] = {}
    for item in declarations:
        dedupe_key = (
            item.normalized_identity,
            item.declaration_kind.value,
            item.raw_version or "",
        )
        unique.setdefault(dedupe_key, item)
    declarations_t = tuple(unique.values())

    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=NUGET_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.NUGET,
        manifest_type=manifest_type,
        parse_status=status,
        classification=classification_for_path(path),
        declaration_count=len(declarations_t),
        unsupported_constructs=tuple(sorted(unsupported)),
        diagnostics=(),
        provenance=_provenance(path, configuration_fingerprint, "nuget_manifest_parse"),
    )
    return manifest, declarations_t


def _declaration(
    *,
    path: str,
    package_name: str,
    raw_version: str | None,
    kind: DependencyDeclarationKind,
    manifest_type: DependencyManifestType,
    group_name: str,
    fingerprint: str,
    method: str,
    is_dependency_management: bool = False,
) -> DependencyDeclarationEvidence:
    return DependencyDeclarationEvidence(
        evidence_id=make_declaration_evidence_id(
            provider_id=NUGET_PROVIDER_ID,
            path=path,
            identity=package_name.lower(),
            kind=kind.value,
            raw_version=raw_version or "",
            profile="",
            line="0",
        ),
        ecosystem=DependencyEcosystem.NUGET,
        manifest_type=manifest_type,
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
        group_name=group_name,
        is_editable=False,
        is_local_path=False,
        is_dependency_management=is_dependency_management,
        source=DependencySourceLocation(
            path=path,
            line_start=None,
            line_end=None,
            snippet=f"{package_name}:{raw_version or ''}"[:200],
        ),
        classification=classification_for_path(path),
        provenance=_provenance(path, fingerprint, method),
    )


def collect_nuget_dependency_bundle(
    *,
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
    ignore_path_markers: Sequence[str],
    max_files: int = 500,
    max_file_chars: int = 500_000,
    configuration_fingerprint: str = "",
) -> DependencyEvidenceBundle:
    paths, excluded = select_nuget_manifest_paths(
        relative_paths,
        ignore_markers=ignore_path_markers,
        max_files=max_files,
    )
    texts = texts_for_paths(paths, file_texts)
    manifests: list[DependencyManifestEvidence] = []
    declarations: list[DependencyDeclarationEvidence] = []
    diagnostics: list[str] = []
    for path in paths:
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"nuget_text_missing:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"nuget_truncated:{path}")
        manifest, decls = parse_nuget_manifest_text(
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
        provider_id=NUGET_PROVIDER_ID,
        provider_version=NUGET_PROVIDER_VERSION,
        ecosystem=DependencyEcosystem.NUGET,
        status=status,
        manifests=manifests_t,
        declarations=declarations_t,
        coverage=coverage,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
