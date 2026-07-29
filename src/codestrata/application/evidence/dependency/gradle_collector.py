"""Conservative Gradle Dependency Evidence collectors (Groovy + Kotlin DSL)."""

from __future__ import annotations

import re
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
    GRADLE_PROVIDER_ID,
    GRADLE_PROVIDER_VERSION,
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

# Static string notations only — never evaluate Gradle.
_STRING_DEP = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|testImplementation|"""
    r"""testCompileOnly|testRuntimeOnly|annotationProcessor|classpath)\s*"""
    r"""[\(]?\s*['"](?P<coord>[^'"]+)['"]""",
    re.MULTILINE,
)
_MAP_DEP = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|testImplementation|"""
    r"""testCompileOnly|testRuntimeOnly|annotationProcessor|classpath)\s*"""
    r"""[\(]?\s*(?:group\s*[:=]\s*['"](?P<group>[^'"]+)['"]\s*,\s*"""
    r"""name\s*[:=]\s*['"](?P<name>[^'"]+)['"]"""
    r"""(?:\s*,\s*version\s*[:=]\s*['"](?P<version>[^'"]+)['"])?)""",
    re.MULTILINE,
)
_KTS_DEP = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|testImplementation|"""
    r"""testCompileOnly|testRuntimeOnly|annotationProcessor)\s*\(\s*"""
    r"""["'](?P<coord>[^"']+)["']\s*\)""",
    re.MULTILINE,
)
_PLUGIN_ID = re.compile(
    r"""id\s*[\(]?\s*['"](?P<id>[^'"]+)['"]\s*[\)]?(?:\s*version\s*['"](?P<version>[^'"]+)['"])?""",
    re.MULTILINE,
)
_DYNAMIC_HINTS = (
    "project(",
    "files(",
    "fileTree(",
    "configurations.",
    "ext.",
    "${",
    "version(",
    "platform(",
    "enforcedPlatform(",
)

_CONFIG_KIND = {
    "implementation": DependencyDeclarationKind.RUNTIME,
    "api": DependencyDeclarationKind.RUNTIME,
    "compileOnly": DependencyDeclarationKind.RUNTIME,
    "runtimeOnly": DependencyDeclarationKind.RUNTIME,
    "testImplementation": DependencyDeclarationKind.TEST,
    "testCompileOnly": DependencyDeclarationKind.TEST,
    "testRuntimeOnly": DependencyDeclarationKind.TEST,
    "annotationProcessor": DependencyDeclarationKind.BUILD,
    "classpath": DependencyDeclarationKind.BUILD,
}


def _split_coord(coord: str) -> tuple[str, str | None]:
    parts = coord.strip().split(":")
    if len(parts) >= 3:
        return f"{parts[0]}:{parts[1]}", parts[2]
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}", None
    return coord.strip(), None


def _line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def _provenance(path: str, fingerprint: str) -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id=GRADLE_PROVIDER_ID,
        provider_version=GRADLE_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method="static_text_parse",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        configuration_fingerprint=fingerprint,
        transformation_chain=("gradle",),
    )


def _declaration(
    *,
    path: str,
    manifest_type: DependencyManifestType,
    identity: str,
    original: str,
    kind: DependencyDeclarationKind,
    raw_version: str | None,
    config: str,
    line: int,
    snippet: str,
    fingerprint: str,
) -> DependencyDeclarationEvidence:
    if raw_version:
        version_availability = DependencyEvidenceAvailability.AVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.RESOLVED
    else:
        version_availability = DependencyEvidenceAvailability.UNAVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.NOT_APPLICABLE
    return DependencyDeclarationEvidence(
        evidence_id=make_declaration_evidence_id(
            provider_id=GRADLE_PROVIDER_ID,
            path=path,
            identity=identity,
            kind=kind.value,
            raw_version=raw_version or "",
            profile="",
            line=str(line),
        ),
        ecosystem=DependencyEcosystem.GRADLE,
        manifest_type=manifest_type,
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=original,
        raw_version=raw_version,
        resolved_version_local=raw_version,
        version_availability=version_availability,
        version_resolution_status=version_resolution_status,
        configuration_name=config,
        source=DependencySourceLocation(
            path=path, line_start=line, line_end=line, snippet=snippet[:200]
        ),
        classification=classification_for_path(path),
        provenance=_provenance(path, fingerprint),
        metadata={
            "version_resolution_contract": "gradle_static_literal_only",
        },
    )


def _unsupported_interpolation(
    *,
    path: str,
    config: str,
    expression: str,
    line: int,
) -> str:
    """Record Gradle interpolation as unsupported coverage, not proven unresolved."""

    return (
        f"{path}:{line}:unsupported_version_resolution:"
        f"gradle_interpolation_uninspected:{config}:{expression}"
    )


def parse_gradle_text(
    *,
    path: str,
    text: str,
    manifest_type: DependencyManifestType,
    configuration_fingerprint: str = "",
) -> tuple[DependencyManifestEvidence, tuple[DependencyDeclarationEvidence, ...]]:
    declarations: list[DependencyDeclarationEvidence] = []
    unsupported: list[str] = []
    unresolved: list[str] = []
    diagnostics: list[str] = []

    for match in _STRING_DEP.finditer(text):
        coord = match.group("coord")
        config = match.group("config")
        line = _line_number(text, match.start())
        if any(hint in coord for hint in ("$", "{", "(", ")")):
            unsupported.append(
                _unsupported_interpolation(
                    path=path, config=config, expression=coord, line=line
                )
            )
            diagnostics.append(
                "version_resolution_unsupported:gradle_property_or_dynamic:"
                f"{path}:{config}:{coord}"
            )
            continue
        identity, version = _split_coord(coord)
        declarations.append(
            _declaration(
                path=path,
                manifest_type=manifest_type,
                identity=identity,
                original=coord,
                kind=_CONFIG_KIND.get(config, DependencyDeclarationKind.UNKNOWN),
                raw_version=version,
                config=config,
                line=line,
                snippet=match.group(0),
                fingerprint=configuration_fingerprint,
            )
        )

    for match in _MAP_DEP.finditer(text):
        group = match.group("group")
        name = match.group("name")
        version = match.group("version")
        config = match.group("config")
        line = _line_number(text, match.start())
        identity = f"{group}:{name}"
        if version and any(hint in version for hint in ("$", "{")):
            unsupported.append(
                _unsupported_interpolation(
                    path=path, config=config, expression=f"{identity}:{version}", line=line
                )
            )
            diagnostics.append(
                "version_resolution_unsupported:gradle_property_or_dynamic:"
                f"{path}:{config}:{identity}:{version}"
            )
            continue
        declarations.append(
            _declaration(
                path=path,
                manifest_type=manifest_type,
                identity=identity,
                original=identity,
                kind=_CONFIG_KIND.get(config, DependencyDeclarationKind.UNKNOWN),
                raw_version=version,
                config=config,
                line=line,
                snippet=match.group(0),
                fingerprint=configuration_fingerprint,
            )
        )

    if manifest_type is DependencyManifestType.BUILD_GRADLE_KTS:
        for match in _KTS_DEP.finditer(text):
            coord = match.group("coord")
            config = match.group("config")
            line = _line_number(text, match.start())
            if any(hint in coord for hint in ("$", "{")):
                unsupported.append(
                    _unsupported_interpolation(
                        path=path, config=config, expression=coord, line=line
                    )
                )
                diagnostics.append(
                    "version_resolution_unsupported:gradle_property_or_dynamic:"
                    f"{path}:{config}:{coord}"
                )
                continue
            identity, version = _split_coord(coord)
            # Avoid duplicates already captured by _STRING_DEP-like patterns.
            if any(
                item.normalized_identity == identity
                and item.configuration_name == config
                and item.source.line_start == line
                for item in declarations
            ):
                continue
            declarations.append(
                _declaration(
                    path=path,
                    manifest_type=manifest_type,
                    identity=identity,
                    original=coord,
                    kind=_CONFIG_KIND.get(config, DependencyDeclarationKind.UNKNOWN),
                    raw_version=version,
                    config=config,
                    line=line,
                    snippet=match.group(0),
                    fingerprint=configuration_fingerprint,
                )
            )

    for match in _PLUGIN_ID.finditer(text):
        plugin_id = match.group("id")
        version = match.group("version")
        declarations.append(
            _declaration(
                path=path,
                manifest_type=manifest_type,
                identity=plugin_id,
                original=plugin_id,
                kind=DependencyDeclarationKind.PLUGIN,
                raw_version=version,
                config="plugin",
                line=_line_number(text, match.start()),
                snippet=match.group(0),
                fingerprint=configuration_fingerprint,
            )
        )

    for index, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("*"):
            continue
        if any(hint in stripped for hint in _DYNAMIC_HINTS):
            # Only flag dependency-ish lines.
            if any(
                token in stripped
                for token in (
                    "implementation",
                    "api",
                    "classpath",
                    "testImplementation",
                    "runtimeOnly",
                    "compileOnly",
                )
            ):
                unsupported.append(f"{path}:{index}:dynamic:{stripped[:120]}")

    ordered = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.source.line_start or 0,
                item.normalized_identity,
                item.declaration_kind.value,
                item.evidence_id,
            ),
        )
    )
    unique_unsupported = tuple(sorted(set(unsupported)))
    unique_unresolved = tuple(sorted(set(unresolved)))
    unique_diagnostics = tuple(sorted(set(diagnostics)))
    status = DependencyParseStatus.SUCCEEDED
    if unique_unsupported or unique_unresolved or unique_diagnostics:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    if not ordered and (unique_unsupported or unique_unresolved or unique_diagnostics):
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=GRADLE_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.GRADLE,
        manifest_type=manifest_type,
        parse_status=status,
        classification=classification_for_path(path),
        declaration_count=len(ordered),
        unsupported_constructs=unique_unsupported,
        unresolved_expressions=unique_unresolved,
        diagnostics=unique_diagnostics,
        provenance=_provenance(path, configuration_fingerprint),
    )
    return manifest, ordered


def collect_gradle_dependency_bundle(
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
        ecosystems=(DependencyEcosystem.GRADLE,),
    )
    texts = texts_for_paths(paths, file_texts)
    manifests: list[DependencyManifestEvidence] = []
    declarations: list[DependencyDeclarationEvidence] = []
    diagnostics: list[str] = []
    for path in paths:
        classified = classify_manifest_basename(path)
        if classified is None:
            continue
        _ecosystem, manifest_type = classified
        if manifest_type not in {
            DependencyManifestType.BUILD_GRADLE,
            DependencyManifestType.BUILD_GRADLE_KTS,
        }:
            continue
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"gradle_text_missing:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"gradle_truncated:{path}")
        manifest, decls = parse_gradle_text(
            path=path,
            text=text,
            manifest_type=manifest_type,
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
        1
        for item in manifests_t
        if item.parse_status is DependencyParseStatus.SUCCEEDED
    )
    partial = sum(
        1
        for item in manifests_t
        if item.parse_status is DependencyParseStatus.PARTIALLY_SUCCEEDED
    )
    failed = sum(
        1 for item in manifests_t if item.parse_status is DependencyParseStatus.FAILED
    )
    unsupported_count = sum(len(item.unsupported_constructs) for item in manifests_t)
    unresolved_count = sum(len(item.unresolved_expressions) for item in manifests_t)
    if manifests_t and (partial or failed or unsupported_count or unresolved_count):
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
        unresolved_expression_count=unresolved_count,
    )
    return DependencyEvidenceBundle(
        provider_id=GRADLE_PROVIDER_ID,
        provider_version=GRADLE_PROVIDER_VERSION,
        ecosystem=DependencyEcosystem.GRADLE,
        status=status,
        manifests=manifests_t,
        declarations=declarations_t,
        coverage=coverage,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
