"""Language detection and raw fact merge helpers for evidence providers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.application.rules.architecture.view_builder import (
    RawPackageFacts,
    collect_raw_package_facts,
)

_LANGUAGE_SUFFIXES: dict[str, frozenset[str]] = {
    "python": frozenset({".py"}),
    "java": frozenset({".java"}),
    "javascript": frozenset({".js", ".jsx", ".ts", ".tsx"}),
    "php": frozenset({".php"}),
    "csharp": frozenset({".cs"}),
}

PROVIDER_PRECEDENCE: tuple[str, ...] = (
    "language.python.core",
    "language.java.core",
    "language.javascript.core",
    "language.php.core",
    "language.csharp.core",
)


def detect_languages_from_paths(relative_paths: Sequence[str]) -> tuple[str, ...]:
    found: set[str] = set()
    for path in relative_paths:
        suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
        for language, suffixes in _LANGUAGE_SUFFIXES.items():
            if suffix in suffixes:
                found.add(language)
    return tuple(sorted(found))


def language_for_path(path: str) -> str | None:
    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
    for language, suffixes in _LANGUAGE_SUFFIXES.items():
        if suffix in suffixes:
            return language
    return None


def suffixes_for_language(language: str) -> frozenset[str]:
    return _LANGUAGE_SUFFIXES.get(language.strip().lower(), frozenset())


def merge_raw_package_facts(parts: Sequence[RawPackageFacts]) -> RawPackageFacts:
    """Deterministically merge language-scoped raw facts."""

    from codestrata.application.rules.architecture.view_builder import stronger_edge_kind

    merged = RawPackageFacts(notes=["merged_raw_package_facts"])
    for part in parts:
        merged.files_considered += part.files_considered
        merged.files_parsed += part.files_parsed
        merged.files_excluded += part.files_excluded
        merged.notes.extend(part.notes)
        for package_id, paths in part.package_files.items():
            merged.package_files[package_id].extend(paths)
            merged.package_layers.setdefault(
                package_id, part.package_layers.get(package_id, "unknown")
            )
            merged.package_layer_confidence.setdefault(
                package_id, part.package_layer_confidence.get(package_id, "low")
            )
        for key, path_set in part.resolved_edges.items():
            merged.resolved_edges[key].update(path_set)
            merged.resolved_symbols[key].update(part.resolved_symbols.get(key, set()))
            merged.resolved_kinds[key] = stronger_edge_kind(
                merged.resolved_kinds.get(key),
                part.resolved_kinds.get(key, "runtime"),
            )
        merged.framework_hits.extend(part.framework_hits)
    for package_id, paths in list(merged.package_files.items()):
        merged.package_files[package_id] = sorted(set(paths))
    merged.framework_hits = sorted(
        {
            (hit.unit_id, hit.framework, hit.symbol, hit.path): hit
            for hit in merged.framework_hits
        }.values(),
        key=lambda item: (item.unit_id, item.symbol, item.path),
    )
    merged.notes = sorted(set(merged.notes))
    return merged


__all__ = [
    "PROVIDER_PRECEDENCE",
    "RawPackageFacts",
    "collect_raw_package_facts",
    "detect_languages_from_paths",
    "language_for_path",
    "merge_raw_package_facts",
    "suffixes_for_language",
]
