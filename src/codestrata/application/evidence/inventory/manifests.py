"""M02 manifest observations: detection vs structural, declared vs resolved."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

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
from codestrata.application.evidence.inventory.catalog import MANIFEST_DEPTH_PINS
from codestrata.application.evidence.inventory.models import (
    ManifestObservation,
    ResolutionObservation,
    SupportKind,
)
from codestrata.application.evidence.inventory.npm import collect_npm_facts
from codestrata.domain.evidence.dependency.enums import DependencyVersionResolutionStatus
from codestrata.services.analyzers.dependency_discovery_analyzer import (
    DependencyDiscoveryAnalyzer,
)

_LOCK_BY_ECOSYSTEM: dict[str, frozenset[str]] = {
    pin.ecosystem: frozenset(name.lower() for name in pin.lockfile_basenames)
    for pin in MANIFEST_DEPTH_PINS
}
_PIN_BY_ECOSYSTEM = {pin.ecosystem: pin for pin in MANIFEST_DEPTH_PINS}


def observe_manifests(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[ManifestObservation, ...]:
    """Observe manifests without installing packages or running scripts."""

    discovery = DependencyDiscoveryAnalyzer()
    detected: list[tuple[str, str, str]] = []
    for relative_path in relative_paths:
        filename = PurePosixPath(relative_path.replace("\\", "/")).name
        definition = discovery.MANIFESTS.get(filename)
        lock = discovery.LOCKFILES.get(filename)
        if definition is None and filename.lower() == "directory.packages.props":
            definition = ("nuget", "manifest")
        if definition is None and filename.lower().endswith((".csproj", ".fsproj", ".vbproj")):
            definition = ("nuget", "manifest")
        if definition is not None:
            ecosystem, kind = definition
            detected.append((relative_path.replace("\\", "/"), ecosystem, kind))
        elif lock is not None:
            ecosystem, kind = lock
            detected.append((relative_path.replace("\\", "/"), ecosystem, kind))

    structural = _structural_observations(relative_paths, file_texts)
    npm_items = tuple(item.observation for item in collect_npm_facts(relative_paths, file_texts))
    by_path = {item.relative_path: item for item in (*structural, *npm_items)}
    observed: list[ManifestObservation] = []
    for path, ecosystem, kind in sorted(detected, key=lambda item: item[0]):
        pin = _PIN_BY_ECOSYSTEM.get(ecosystem)
        if path in by_path:
            observed.append(by_path[path])
            continue
        support = pin.support if pin is not None else SupportKind.DETECTION_ONLY
        resolution = _resolution_for_detection(path, ecosystem, kind, relative_paths)
        observed.append(
            ManifestObservation(
                relative_path=path,
                ecosystem=ecosystem,
                manifest_kind=kind,
                support=support if kind != "lockfile" else SupportKind.DETECTION_ONLY,
                resolution=resolution,
                parser_version=pin.structural_provider_id if pin is not None else None,
                diagnostics=_workspace_diagnostics(path, file_texts),
            )
        )
    return tuple(observed)


def _structural_observations(
    relative_paths: Sequence[str],
    file_texts: Mapping[str, str],
) -> tuple[ManifestObservation, ...]:
    collectors = (
        collect_maven_dependency_bundle,
        collect_gradle_dependency_bundle,
        collect_python_dependency_bundle,
        collect_composer_dependency_bundle,
        collect_nuget_dependency_bundle,
    )
    items: list[ManifestObservation] = []
    for collector in collectors:
        bundle = collector(
            relative_paths=relative_paths,
            file_texts=file_texts,
            ignore_path_markers=DEFAULT_DEPENDENCY_IGNORE_MARKERS,
        )
        identities = [item.normalized_identity for item in bundle.declarations]
        duplicates = tuple(
            sorted(identity for identity, count in Counter(identities).items() if count > 1)
        )
        declared_by_path: dict[str, int] = {}
        resolved_by_path: dict[str, int] = {}
        for declaration in bundle.declarations:
            path = declaration.source.path
            declared_by_path[path] = declared_by_path.get(path, 0) + 1
            if declaration.version_resolution_status is DependencyVersionResolutionStatus.RESOLVED:
                resolved_by_path[path] = resolved_by_path.get(path, 0) + 1
        for manifest in bundle.manifests:
            pin = _PIN_BY_ECOSYSTEM.get(manifest.ecosystem.value)
            resolution = pin.resolution if pin is not None else ResolutionObservation.UNKNOWN
            items.append(
                ManifestObservation(
                    relative_path=manifest.path,
                    ecosystem=manifest.ecosystem.value,
                    manifest_kind="manifest",
                    support=SupportKind.STRUCTURAL,
                    resolution=resolution,
                    declared_count=declared_by_path.get(manifest.path, 0),
                    resolved_count=resolved_by_path.get(manifest.path, 0),
                    parser_version=bundle.provider_version,
                    duplicate_coordinates=duplicates,
                    diagnostics=tuple(manifest.diagnostics),
                )
            )
    return tuple(items)


def _lock_present(ecosystem: str, relative_paths: Sequence[str]) -> bool:
    names = _LOCK_BY_ECOSYSTEM.get(ecosystem, frozenset())
    if not names:
        return False
    found = {PurePosixPath(path.replace("\\", "/")).name.lower() for path in relative_paths}
    return bool(found.intersection(names))


def _resolution_for_detection(
    _path: str,
    ecosystem: str,
    kind: str,
    relative_paths: Sequence[str],
) -> ResolutionObservation:
    pin = _PIN_BY_ECOSYSTEM.get(ecosystem)
    if pin is None:
        return ResolutionObservation.UNKNOWN
    if pin.support is SupportKind.DETECTION_ONLY:
        return ResolutionObservation.UNKNOWN
    if kind == "lockfile":
        return ResolutionObservation.UNKNOWN
    if pin.lockfile_basenames and not _lock_present(ecosystem, relative_paths):
        return ResolutionObservation.UNKNOWN
    return pin.resolution


def _workspace_diagnostics(
    path: str,
    file_texts: Mapping[str, str],
) -> tuple[str, ...]:
    name = PurePosixPath(path).name.lower()
    if name != "package.json":
        return ()
    text = file_texts.get(path, "")
    if '"workspaces"' in text:
        return ("workspace_packages_detection_only",)
    return ()
