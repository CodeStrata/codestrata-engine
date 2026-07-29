"""Path-based module resolution for Repository Graph structure extraction.

Nested build/dependency manifests define initial module roots. A root-level
manifest does not create a module: the repository node already represents the
workspace root, and directories are not graph nodes in this milestone.

Ownership uses the deepest matching module root so nested modules do not
double-claim files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from codestrata.domain.repository.manifests import RepositoryManifest
from codestrata.domain.repository.paths import RepositoryPath
from codestrata.services.repository_graph.enums import ExtractionDiagnosticSeverity
from codestrata.services.repository_graph.results import ExtractionDiagnostic

# Exact basenames (lowered) and their build-system labels, ordered by priority
# when multiple markers appear at the same module root.
_EXACT_MARKERS: tuple[tuple[str, str], ...] = (
    ("pom.xml", "maven"),
    ("build.gradle.kts", "gradle"),
    ("build.gradle", "gradle"),
    ("settings.gradle.kts", "gradle"),
    ("settings.gradle", "gradle"),
    ("package.json", "npm"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("setup.cfg", "python"),
    ("composer.json", "composer"),
    ("go.mod", "go"),
    ("cargo.toml", "cargo"),
)

# Suffix markers (lowered), also priority-ordered after exact names.
_SUFFIX_MARKERS: tuple[tuple[str, str], ...] = (
    (".csproj", "dotnet"),
    (".fsproj", "dotnet"),
    (".vbproj", "dotnet"),
)

EXTRACTOR_ID = "repository-structure"


@dataclass(frozen=True, slots=True)
class ResolvedModule:
    """One module root identified from inventory marker files."""

    path: RepositoryPath
    name: str
    build_system: str
    marker_path: RepositoryPath
    marker_paths: tuple[RepositoryPath, ...]


@dataclass(frozen=True, slots=True)
class ModuleResolution:
    """Resolved modules plus deepest-module file ownership."""

    modules: tuple[ResolvedModule, ...]
    file_module_paths: Mapping[str, str | None]
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()


class RepositoryModuleResolver(Protocol):
    """Derive structural modules from a repository inventory."""

    def resolve(self, manifest: RepositoryManifest) -> ModuleResolution:
        """Return modules and per-file ownership for ``manifest``."""


class PathBasedModuleResolver:
    """Deterministic module roots from nested build/dependency manifests."""

    def resolve(self, manifest: RepositoryManifest) -> ModuleResolution:
        markers_by_root: dict[str, list[RepositoryPath]] = {}
        for entry in manifest.files:
            marker = _match_marker(entry.path.root)
            if marker is None:
                continue
            root = _module_root_for_marker(entry.path.root)
            if root is None:
                # Root-level manifests do not create a module node.
                continue
            markers_by_root.setdefault(root, []).append(entry.path)

        diagnostics: list[ExtractionDiagnostic] = []
        modules: list[ResolvedModule] = []
        for root in sorted(markers_by_root):
            marker_paths = tuple(sorted(markers_by_root[root], key=lambda path: path.root))
            build_system, selected, warning = _select_build_system(marker_paths)
            if warning is not None:
                diagnostics.append(warning)
            modules.append(
                ResolvedModule(
                    path=RepositoryPath(root),
                    name=PurePosixPath(root).name,
                    build_system=build_system,
                    marker_path=selected,
                    marker_paths=marker_paths,
                )
            )

        module_paths = tuple(module.path.root for module in modules)
        file_owners: dict[str, str | None] = {}
        for entry in manifest.files:
            file_owners[entry.path.root] = _deepest_owner(entry.path.root, module_paths)

        return ModuleResolution(
            modules=tuple(modules),
            file_module_paths=file_owners,
            diagnostics=tuple(diagnostics),
        )


def direct_child_modules(
    modules: Sequence[ResolvedModule],
) -> Mapping[str, tuple[str, ...]]:
    """Map each module path to its direct child module paths."""

    roots = [module.path.root for module in modules]
    children: dict[str, list[str]] = {root: [] for root in roots}
    for child in roots:
        parent = _direct_parent_module(child, roots)
        if parent is not None:
            children[parent].append(child)
    return {root: tuple(sorted(kids)) for root, kids in children.items()}


def top_level_modules(modules: Sequence[ResolvedModule]) -> tuple[ResolvedModule, ...]:
    """Return modules that are not nested under another resolved module."""

    roots = [module.path.root for module in modules]
    return tuple(
        module for module in modules if _direct_parent_module(module.path.root, roots) is None
    )


def _match_marker(path: str) -> str | None:
    name = PurePosixPath(path).name.lower()
    for exact, _system in _EXACT_MARKERS:
        if name == exact:
            return exact
    for suffix, _system in _SUFFIX_MARKERS:
        if name.endswith(suffix):
            return suffix
    return None


def _module_root_for_marker(marker_path: str) -> str | None:
    parent = PurePosixPath(marker_path).parent
    if str(parent) in (".", ""):
        return None
    return parent.as_posix()


def _select_build_system(
    marker_paths: tuple[RepositoryPath, ...],
) -> tuple[str, RepositoryPath, ExtractionDiagnostic | None]:
    ranked: list[tuple[int, RepositoryPath, str]] = []
    for marker in marker_paths:
        name = PurePosixPath(marker.root).name.lower()
        for index, (exact, system) in enumerate(_EXACT_MARKERS):
            if name == exact:
                ranked.append((index, marker, system))
                break
        else:
            for index, (suffix, system) in enumerate(_SUFFIX_MARKERS):
                if name.endswith(suffix):
                    # Keep suffix markers after all exact markers in priority.
                    ranked.append((len(_EXACT_MARKERS) + index, marker, system))
                    break
    if not ranked:
        raise ValueError("expected at least one module marker")
    ranked.sort(key=lambda item: (item[0], item[1].root))
    _priority, selected, system = ranked[0]
    warning: ExtractionDiagnostic | None = None
    systems = {item[2] for item in ranked}
    if len(marker_paths) > 1 or len(systems) > 1:
        warning = ExtractionDiagnostic(
            severity=ExtractionDiagnosticSeverity.WARNING,
            code="multiple-module-markers",
            message=(
                "multiple module markers at the same root; "
                f"selected build_system '{system}' from '{selected.root}'"
            ),
            path=selected.root,
            extractor_id=EXTRACTOR_ID,
        )
    return system, selected, warning


def _deepest_owner(file_path: str, module_roots: Sequence[str]) -> str | None:
    owners = [
        root for root in module_roots if file_path == root or file_path.startswith(f"{root}/")
    ]
    if not owners:
        return None
    return max(owners, key=lambda root: (root.count("/"), len(root), root))


def _direct_parent_module(module_path: str, module_roots: Sequence[str]) -> str | None:
    ancestors = [
        root for root in module_roots if module_path != root and module_path.startswith(f"{root}/")
    ]
    if not ancestors:
        return None
    return max(ancestors, key=lambda root: (root.count("/"), len(root), root))
