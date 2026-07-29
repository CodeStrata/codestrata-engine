"""Maven pom.xml structural Dependency Evidence collector."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence

from codestrata.application.evidence.dependency.normalize import (
    normalize_maven_identity,
    resolve_local_properties,
)
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
    MAVEN_PROVIDER_ID,
    MAVEN_PROVIDER_VERSION,
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

_SCOPE_TO_KIND = {
    "compile": DependencyDeclarationKind.RUNTIME,
    "runtime": DependencyDeclarationKind.RUNTIME,
    "provided": DependencyDeclarationKind.RUNTIME,
    "test": DependencyDeclarationKind.TEST,
    "system": DependencyDeclarationKind.RUNTIME,
    "import": DependencyDeclarationKind.PLATFORM,
}


def _xml_namespace(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[0][1:]
    return ""


def _path(namespace: str, *parts: str) -> str:
    if namespace:
        return "/".join(f"{{{namespace}}}{part}" for part in parts)
    return "/".join(parts)


def _text(element: ET.Element | None, namespace: str, name: str) -> str | None:
    if element is None:
        return None
    child = element.find(_path(namespace, name))
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _properties(root: ET.Element, namespace: str) -> dict[str, str]:
    props_el = root.find(_path(namespace, "properties"))
    if props_el is None:
        return {}
    properties: dict[str, str] = {}
    for child in props_el:
        key = child.tag.split("}")[-1]
        if child.text and child.text.strip():
            properties[key] = child.text.strip()
    # Project coordinates as pseudo-properties when present.
    group = _text(root, namespace, "groupId")
    artifact = _text(root, namespace, "artifactId")
    version = _text(root, namespace, "version")
    if group:
        properties.setdefault("project.groupId", group)
    if artifact:
        properties.setdefault("project.artifactId", artifact)
    if version:
        properties.setdefault("project.version", version)
        properties.setdefault("version", version)
    parent = root.find(_path(namespace, "parent"))
    if parent is not None:
        parent_version = _text(parent, namespace, "version")
        if parent_version:
            properties.setdefault("project.parent.version", parent_version)
    return properties


def _line_of(text: str, needle: str) -> int | None:
    if not needle:
        return None
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _kind_for_scope(scope: str | None, *, optional: bool) -> DependencyDeclarationKind:
    if optional:
        return DependencyDeclarationKind.OPTIONAL
    if scope is None:
        return DependencyDeclarationKind.RUNTIME
    return _SCOPE_TO_KIND.get(scope.strip().lower(), DependencyDeclarationKind.UNKNOWN)


def _parse_dependency_element(
    element: ET.Element,
    *,
    namespace: str,
    path: str,
    text: str,
    properties: dict[str, str],
    profile: str | None,
    is_management: bool,
) -> tuple[DependencyDeclarationEvidence | None, tuple[str, ...]]:
    unresolved: list[str] = []
    group_id = _text(element, namespace, "groupId")
    artifact_id = _text(element, namespace, "artifactId")
    identity = normalize_maven_identity(group_id, artifact_id)
    if identity is None:
        return None, ()
    raw_version = _text(element, namespace, "version")
    resolved, ok = resolve_local_properties(raw_version, properties)
    if raw_version and not ok:
        unresolved.append(f"{identity}:{raw_version}")
    scope = _text(element, namespace, "scope")
    optional_text = (_text(element, namespace, "optional") or "").lower()
    optional = optional_text in {"true", "1", "yes"}
    kind = (
        DependencyDeclarationKind.DEPENDENCY_MANAGEMENT
        if is_management
        else _kind_for_scope(scope, optional=optional)
    )
    line = _line_of(text, artifact_id or identity)
    if not raw_version:
        version_availability = DependencyEvidenceAvailability.UNAVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.NOT_APPLICABLE
        resolved_local = None
    elif ok and resolved is not None:
        version_availability = DependencyEvidenceAvailability.AVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.RESOLVED
        resolved_local = resolved
    else:
        # Supported Maven local property contract was inspected; property missing.
        version_availability = DependencyEvidenceAvailability.UNAVAILABLE
        version_resolution_status = (
            DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
        )
        resolved_local = None
    provenance = EvidenceProvenance(
        provider_id=MAVEN_PROVIDER_ID,
        provider_version=MAVEN_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method="xml_parse",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        transformation_chain=("pom.xml",),
    )
    evidence = DependencyDeclarationEvidence(
        evidence_id=make_declaration_evidence_id(
            provider_id=MAVEN_PROVIDER_ID,
            path=path,
            identity=identity,
            kind=kind.value,
            raw_version=raw_version or "",
            profile=profile or "",
            line=str(line or 0),
        ),
        ecosystem=DependencyEcosystem.MAVEN,
        manifest_type=DependencyManifestType.POM_XML,
        declaration_kind=kind,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=resolved_local,
        version_availability=version_availability,
        version_resolution_status=version_resolution_status,
        optional=optional,
        profile=profile,
        is_dependency_management=is_management,
        configuration_name=scope,
        source=DependencySourceLocation(
            path=path,
            line_start=line,
            line_end=line,
            snippet=f"{identity}:{raw_version}" if raw_version else identity,
        ),
        classification=classification_for_path(path),
        provenance=provenance,
        metadata={
            "group_id": group_id or "",
            "artifact_id": artifact_id or "",
            "version_resolution_contract": "maven_local_pom_properties",
        },
    )
    return evidence, tuple(unresolved)


def _parse_plugin_element(
    element: ET.Element,
    *,
    namespace: str,
    path: str,
    text: str,
    properties: dict[str, str],
    profile: str | None,
) -> tuple[DependencyDeclarationEvidence | None, tuple[str, ...]]:
    group_id = _text(element, namespace, "groupId") or "org.apache.maven.plugins"
    artifact_id = _text(element, namespace, "artifactId")
    identity = normalize_maven_identity(group_id, artifact_id)
    if identity is None:
        return None, ()
    raw_version = _text(element, namespace, "version")
    resolved, ok = resolve_local_properties(raw_version, properties)
    unresolved: tuple[str, ...] = ()
    if raw_version and not ok:
        unresolved = (f"plugin:{identity}:{raw_version}",)
    line = _line_of(text, artifact_id or identity)
    if not raw_version:
        version_availability = DependencyEvidenceAvailability.UNAVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.NOT_APPLICABLE
        resolved_local = None
    elif ok and resolved is not None:
        version_availability = DependencyEvidenceAvailability.AVAILABLE
        version_resolution_status = DependencyVersionResolutionStatus.RESOLVED
        resolved_local = resolved
    else:
        version_availability = DependencyEvidenceAvailability.UNAVAILABLE
        version_resolution_status = (
            DependencyVersionResolutionStatus.PROVEN_UNRESOLVED
        )
        resolved_local = None
    provenance = EvidenceProvenance(
        provider_id=MAVEN_PROVIDER_ID,
        provider_version=MAVEN_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method="xml_parse",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        transformation_chain=("pom.xml", "plugin"),
    )
    evidence = DependencyDeclarationEvidence(
        evidence_id=make_declaration_evidence_id(
            provider_id=MAVEN_PROVIDER_ID,
            path=path,
            identity=identity,
            kind=DependencyDeclarationKind.PLUGIN.value,
            raw_version=raw_version or "",
            profile=profile or "",
            line=str(line or 0),
        ),
        ecosystem=DependencyEcosystem.MAVEN,
        manifest_type=DependencyManifestType.POM_XML,
        declaration_kind=DependencyDeclarationKind.PLUGIN,
        normalized_identity=identity,
        original_identity=identity,
        raw_version=raw_version,
        resolved_version_local=resolved_local,
        version_availability=version_availability,
        version_resolution_status=version_resolution_status,
        profile=profile,
        source=DependencySourceLocation(
            path=path,
            line_start=line,
            line_end=line,
            snippet=f"plugin:{identity}",
        ),
        classification=classification_for_path(path),
        provenance=provenance,
        metadata={"version_resolution_contract": "maven_local_pom_properties"},
    )
    return evidence, unresolved


def _collect_from_container(
    container: ET.Element,
    *,
    namespace: str,
    path: str,
    text: str,
    properties: dict[str, str],
    profile: str | None,
) -> tuple[list[DependencyDeclarationEvidence], list[str], list[str]]:
    declarations: list[DependencyDeclarationEvidence] = []
    unresolved: list[str] = []
    unsupported: list[str] = []

    deps = container.find(_path(namespace, "dependencies"))
    if deps is not None:
        for dep in deps.findall(_path(namespace, "dependency")):
            item, unresolved_items = _parse_dependency_element(
                dep,
                namespace=namespace,
                path=path,
                text=text,
                properties=properties,
                profile=profile,
                is_management=False,
            )
            if item is not None:
                declarations.append(item)
            unresolved.extend(unresolved_items)

    mgmt = container.find(_path(namespace, "dependencyManagement"))
    if mgmt is not None:
        managed = mgmt.find(_path(namespace, "dependencies"))
        if managed is not None:
            for dep in managed.findall(_path(namespace, "dependency")):
                item, unresolved_items = _parse_dependency_element(
                    dep,
                    namespace=namespace,
                    path=path,
                    text=text,
                    properties=properties,
                    profile=profile,
                    is_management=True,
                )
                if item is not None:
                    declarations.append(item)
                unresolved.extend(unresolved_items)

    build = container.find(_path(namespace, "build"))
    if build is not None:
        plugins = build.find(_path(namespace, "plugins"))
        if plugins is not None:
            for plugin in plugins.findall(_path(namespace, "plugin")):
                item, unresolved_items = _parse_plugin_element(
                    plugin,
                    namespace=namespace,
                    path=path,
                    text=text,
                    properties=properties,
                    profile=profile,
                )
                if item is not None:
                    declarations.append(item)
                unresolved.extend(unresolved_items)
        plugin_mgmt = build.find(_path(namespace, "pluginManagement"))
        if plugin_mgmt is not None:
            unsupported.append(f"{path}:pluginManagement_present")

    return declarations, unresolved, unsupported


def parse_pom_text(
    *,
    path: str,
    text: str,
    configuration_fingerprint: str = "",
) -> tuple[
    DependencyManifestEvidence,
    tuple[DependencyDeclarationEvidence, ...],
]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        provenance = EvidenceProvenance(
            provider_id=MAVEN_PROVIDER_ID,
            provider_version=MAVEN_PROVIDER_VERSION,
            source_analyzer="dependency_evidence",
            extraction_method="xml_parse",
            origin=EvidenceOrigin.MANIFEST,
            source_path=path,
            notes=(f"parse_error:{error}",),
            configuration_fingerprint=configuration_fingerprint,
        )
        manifest = DependencyManifestEvidence(
            evidence_id=make_manifest_evidence_id(
                provider_id=MAVEN_PROVIDER_ID, path=path
            ),
            path=path,
            ecosystem=DependencyEcosystem.MAVEN,
            manifest_type=DependencyManifestType.POM_XML,
            parse_status=DependencyParseStatus.FAILED,
            classification=classification_for_path(path),
            diagnostics=(f"maven_parse_error:{error}",),
            provenance=provenance,
        )
        return manifest, ()

    namespace = _xml_namespace(root)
    properties = _properties(root, namespace)
    declarations: list[DependencyDeclarationEvidence] = []
    unresolved: list[str] = []
    unsupported: list[str] = []

    root_decls, root_unresolved, root_unsupported = _collect_from_container(
        root,
        namespace=namespace,
        path=path,
        text=text,
        properties=properties,
        profile=None,
    )
    declarations.extend(root_decls)
    unresolved.extend(root_unresolved)
    unsupported.extend(root_unsupported)

    profiles = root.find(_path(namespace, "profiles"))
    if profiles is not None:
        for profile_el in profiles.findall(_path(namespace, "profile")):
            profile_id = _text(profile_el, namespace, "id") or "unnamed-profile"
            profile_decls, profile_unresolved, profile_unsupported = (
                _collect_from_container(
                    profile_el,
                    namespace=namespace,
                    path=path,
                    text=text,
                    properties=properties,
                    profile=profile_id,
                )
            )
            declarations.extend(profile_decls)
            unresolved.extend(profile_unresolved)
            unsupported.extend(profile_unsupported)

    # Parent POM not fetched — record as unresolved context when parent present.
    parent = root.find(_path(namespace, "parent"))
    if parent is not None:
        parent_ga = normalize_maven_identity(
            _text(parent, namespace, "groupId"),
            _text(parent, namespace, "artifactId"),
        )
        if parent_ga:
            unsupported.append(f"{path}:parent_not_fetched:{parent_ga}")

    ordered = tuple(
        sorted(
            declarations,
            key=lambda item: (
                item.path if False else item.source.path,
                item.normalized_identity,
                item.declaration_kind.value,
                item.profile or "",
                item.evidence_id,
            ),
        )
    )
    unique_unresolved = tuple(sorted(set(unresolved)))
    unique_unsupported = tuple(sorted(set(unsupported)))
    status = DependencyParseStatus.SUCCEEDED
    if unique_unresolved or unique_unsupported:
        status = DependencyParseStatus.PARTIALLY_SUCCEEDED
    provenance = EvidenceProvenance(
        provider_id=MAVEN_PROVIDER_ID,
        provider_version=MAVEN_PROVIDER_VERSION,
        source_analyzer="dependency_evidence",
        extraction_method="xml_parse",
        origin=EvidenceOrigin.MANIFEST,
        source_path=path,
        configuration_fingerprint=configuration_fingerprint,
    )
    manifest = DependencyManifestEvidence(
        evidence_id=make_manifest_evidence_id(provider_id=MAVEN_PROVIDER_ID, path=path),
        path=path,
        ecosystem=DependencyEcosystem.MAVEN,
        manifest_type=DependencyManifestType.POM_XML,
        parse_status=status,
        classification=classification_for_path(path),
        declaration_count=len(ordered),
        unsupported_constructs=unique_unsupported,
        unresolved_expressions=unique_unresolved,
        provenance=provenance,
    )
    return manifest, ordered


def collect_maven_dependency_bundle(
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
        ecosystems=(DependencyEcosystem.MAVEN,),
    )
    texts = texts_for_paths(paths, file_texts)
    manifests: list[DependencyManifestEvidence] = []
    declarations: list[DependencyDeclarationEvidence] = []
    diagnostics: list[str] = []
    for path in paths:
        classified = classify_manifest_basename(path)
        if classified is None or classified[1] is not DependencyManifestType.POM_XML:
            continue
        text = texts.get(path)
        if text is None:
            diagnostics.append(f"maven_text_missing:{path}")
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
            diagnostics.append(f"maven_truncated:{path}")
        manifest, decls = parse_pom_text(
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
                item.normalized_identity,
                item.declaration_kind.value,
                item.profile or "",
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
    if failed and not parsed and not partial:
        status = DependencyParseStatus.FAILED
    elif partial or failed or unsupported_count or unresolved_count:
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
        provider_id=MAVEN_PROVIDER_ID,
        provider_version=MAVEN_PROVIDER_VERSION,
        ecosystem=DependencyEcosystem.MAVEN,
        status=status,
        manifests=manifests_t,
        declarations=declarations_t,
        coverage=coverage,
        diagnostics=tuple(sorted(set(diagnostics))),
    )
