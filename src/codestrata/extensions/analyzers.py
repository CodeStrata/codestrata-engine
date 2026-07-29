"""Opt-in analyzer extension discovery and loading."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points

from codestrata.extensions.namespaces import assert_third_party_analyzer_id
from codestrata.extensions.version import EXTENSION_API_VERSION, extension_api_compatible
from codestrata.services.contracts import Analyzer

ENTRY_POINT_GROUP = "codestrata.analyzer_extensions"


@dataclass(frozen=True, slots=True)
class LoadedAnalyzerExtension:
    """A discovered analyzer extension ready for pipeline inclusion."""

    id: str
    api_version: str
    analyzer: Analyzer
    source: str


@dataclass(frozen=True, slots=True)
class AnalyzerExtensionIssue:
    """Diagnostic for a rejected or conflicting analyzer extension."""

    id: str
    kind: str  # version_mismatch | duplicate | load_error | reserved | not_found
    detail: str


def discover_analyzer_extensions(
    *,
    enabled: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[LoadedAnalyzerExtension], list[AnalyzerExtensionIssue]]:
    """Load allowlisted analyzer extensions from entry points.

    When ``enabled`` is empty or None, no third-party analyzers are loaded
    (Community default: built-ins only).
    """

    allow = [item.strip() for item in (enabled or ()) if item and item.strip()]
    if not allow:
        return [], []

    allow_set = set(allow)
    loaded: list[LoadedAnalyzerExtension] = []
    issues: list[AnalyzerExtensionIssue] = []
    seen: dict[str, str] = {}

    discovered_ids: set[str] = set()

    for ep in entry_points().select(group=ENTRY_POINT_GROUP):
        source = f"entry_point:{ep.name}"
        try:
            loaded_obj = ep.load()
        except Exception as error:  # noqa: BLE001
            issues.append(
                AnalyzerExtensionIssue(
                    id=ep.name,
                    kind="load_error",
                    detail=f"Failed to load {source}: {error}",
                )
            )
            continue

        try:
            extension_id = str(loaded_obj.id)
            api_version = str(getattr(loaded_obj, "api_version", ""))
            create = loaded_obj.create
        except Exception as error:  # noqa: BLE001
            issues.append(
                AnalyzerExtensionIssue(
                    id=ep.name,
                    kind="load_error",
                    detail=f"Invalid AnalyzerExtension at {source}: {error}",
                )
            )
            continue

        discovered_ids.add(extension_id)

        if extension_id not in allow_set:
            continue

        try:
            assert_third_party_analyzer_id(extension_id)
        except ValueError as error:
            issues.append(
                AnalyzerExtensionIssue(
                    id=extension_id,
                    kind="reserved",
                    detail=str(error),
                )
            )
            continue

        if not extension_api_compatible(api_version):
            issues.append(
                AnalyzerExtensionIssue(
                    id=extension_id,
                    kind="version_mismatch",
                    detail=(
                        f"Extension API {api_version!r} incompatible with Engine "
                        f"{EXTENSION_API_VERSION}"
                    ),
                )
            )
            continue

        if extension_id in seen:
            issues.append(
                AnalyzerExtensionIssue(
                    id=extension_id,
                    kind="duplicate",
                    detail=f"Duplicate id from {source} (also {seen[extension_id]})",
                )
            )
            continue

        if not callable(create):
            issues.append(
                AnalyzerExtensionIssue(
                    id=extension_id,
                    kind="load_error",
                    detail=f"{source}: create is not callable",
                )
            )
            continue

        try:
            analyzer = create()
        except Exception as error:  # noqa: BLE001
            issues.append(
                AnalyzerExtensionIssue(
                    id=extension_id,
                    kind="load_error",
                    detail=f"{source}: create() failed: {error}",
                )
            )
            continue

        seen[extension_id] = source
        loaded.append(
            LoadedAnalyzerExtension(
                id=extension_id,
                api_version=api_version,
                analyzer=analyzer,
                source=source,
            )
        )

    for requested in allow:
        if requested not in discovered_ids and requested not in seen:
            # May already have an issue (reserved/version) if discovered under another path
            if any(item.id == requested for item in issues):
                continue
            issues.append(
                AnalyzerExtensionIssue(
                    id=requested,
                    kind="not_found",
                    detail=(
                        f"Enabled analyzer {requested!r} was not found on entry point "
                        f"group {ENTRY_POINT_GROUP!r}. Install the providing package "
                        "or fix the id."
                    ),
                )
            )

    # Preserve allowlist order among successfully loaded extensions.
    order = {extension_id: index for index, extension_id in enumerate(allow)}
    loaded.sort(key=lambda item: order.get(item.id, len(order)))
    return loaded, issues


def resolve_enabled_analyzers(
    enabled: list[str] | tuple[str, ...] | None,
    *,
    strict: bool = True,
) -> list[Analyzer]:
    """Return analyzer instances for the allowlist.

    When ``strict`` is True (assess path), any issue raises ``ValueError``.
    """

    loaded, issues = discover_analyzer_extensions(enabled=enabled)
    if issues and strict:
        detail = "; ".join(f"{item.id}: {item.detail}" for item in issues)
        raise ValueError(f"Analyzer extension configuration error: {detail}")
    return [item.analyzer for item in loaded]


__all__ = [
    "ENTRY_POINT_GROUP",
    "AnalyzerExtensionIssue",
    "LoadedAnalyzerExtension",
    "discover_analyzer_extensions",
    "resolve_enabled_analyzers",
]
