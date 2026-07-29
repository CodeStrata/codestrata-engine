"""Extension inventory for ``codestrata extensions list`` and doctor."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from codestrata.extensions.analyzers import (
    ENTRY_POINT_GROUP as ANALYZER_GROUP,
)
from codestrata.extensions.analyzers import (
    discover_analyzer_extensions,
)
from codestrata.extensions.assess_ai import (
    ENTRY_POINT_GROUP as ASSESS_AI_GROUP,
)
from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
)
from codestrata.extensions.renderers import (
    ENTRY_POINT_GROUP as RENDERER_GROUP,
)
from codestrata.extensions.renderers import (
    get_report_renderer_registry,
)
from codestrata.extensions.version import EXTENSION_API_VERSION


@dataclass(frozen=True, slots=True)
class ExtensionInventoryItem:
    """One discovered or configured extension surface."""

    kind: str
    extension_id: str
    status: str
    detail: str
    api_version: str | None = None


def _ep_names(group: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for ep in entry_points().select(group=group):
        dist = ""
        try:
            dist = ep.dist.name if ep.dist is not None else ""
        except Exception:  # noqa: BLE001
            dist = ""
        rows.append((ep.name, dist))
    return rows


def build_extension_inventory(
    *,
    enabled_analyzers: list[str] | tuple[str, ...] | None = None,
    disabled_cli: list[str] | tuple[str, ...] | None = None,
    disabled_mcp: list[str] | tuple[str, ...] | None = None,
) -> list[ExtensionInventoryItem]:
    """Collect loaded / disabled / mismatch / duplicate extension diagnostics."""

    items: list[ExtensionInventoryItem] = []
    disabled_cli_set = {name.strip() for name in (disabled_cli or ()) if name.strip()}
    disabled_mcp_set = {name.strip() for name in (disabled_mcp or ()) if name.strip()}

    items.append(
        ExtensionInventoryItem(
            kind="engine",
            extension_id="extension-api",
            status="loaded",
            detail=f"Engine Extension API {EXTENSION_API_VERSION}",
            api_version=EXTENSION_API_VERSION,
        )
    )

    for name, dist in _ep_names("codestrata.cli_extensions"):
        if name in disabled_cli_set:
            items.append(
                ExtensionInventoryItem(
                    kind="cli",
                    extension_id=name,
                    status="disabled",
                    detail=f"Disabled via [extensions.cli].disabled ({dist or 'unknown'})",
                )
            )
        else:
            items.append(
                ExtensionInventoryItem(
                    kind="cli",
                    extension_id=name,
                    status="loaded",
                    detail=f"Entry point present ({dist or 'unknown'})",
                )
            )

    for name in sorted(disabled_cli_set):
        if not any(item.kind == "cli" and item.extension_id == name for item in items):
            items.append(
                ExtensionInventoryItem(
                    kind="cli",
                    extension_id=name,
                    status="disabled",
                    detail="Listed in [extensions.cli].disabled but not installed",
                )
            )

    for name, dist in _ep_names("codestrata.mcp_extensions"):
        if name in disabled_mcp_set:
            items.append(
                ExtensionInventoryItem(
                    kind="mcp",
                    extension_id=name,
                    status="disabled",
                    detail=f"Disabled via [extensions.mcp].disabled ({dist or 'unknown'})",
                )
            )
        else:
            items.append(
                ExtensionInventoryItem(
                    kind="mcp",
                    extension_id=name,
                    status="loaded",
                    detail=f"Entry point present ({dist or 'unknown'})",
                )
            )

    for name in sorted(disabled_mcp_set):
        if not any(item.kind == "mcp" and item.extension_id == name for item in items):
            items.append(
                ExtensionInventoryItem(
                    kind="mcp",
                    extension_id=name,
                    status="disabled",
                    detail="Listed in [extensions.mcp].disabled but not installed",
                )
            )

    assess_registry = get_assess_ai_provider_registry()
    for provider_id in assess_registry.list_providers():
        items.append(
            ExtensionInventoryItem(
                kind="assess_ai",
                extension_id=provider_id,
                status="loaded",
                detail="Registered assess AI provider",
                api_version=assess_registry.api_version_for(provider_id),
            )
        )
    for name, dist in _ep_names(ASSESS_AI_GROUP):
        items.append(
            ExtensionInventoryItem(
                kind="assess_ai",
                extension_id=f"entry:{name}",
                status="loaded",
                detail=f"Assess AI entry point ({dist or 'unknown'})",
            )
        )

    for name, dist in _ep_names("codestrata.ai_provider_extensions"):
        items.append(
            ExtensionInventoryItem(
                kind="rag_ai",
                extension_id=name,
                status="loaded",
                detail=f"RAG AI entry point ({dist or 'unknown'})",
            )
        )

    renderer_registry = get_report_renderer_registry()
    for renderer_id in renderer_registry.list_ids():
        items.append(
            ExtensionInventoryItem(
                kind="renderer",
                extension_id=renderer_id,
                status="loaded",
                detail="Registered report renderer",
                api_version=EXTENSION_API_VERSION,
            )
        )
    for name, dist in _ep_names(RENDERER_GROUP):
        items.append(
            ExtensionInventoryItem(
                kind="renderer",
                extension_id=f"entry:{name}",
                status="loaded",
                detail=f"Renderer entry point ({dist or 'unknown'})",
            )
        )

    loaded, issues = discover_analyzer_extensions(enabled=enabled_analyzers)
    for item in loaded:
        items.append(
            ExtensionInventoryItem(
                kind="analyzer",
                extension_id=item.id,
                status="loaded",
                detail=item.source,
                api_version=item.api_version,
            )
        )
    for issue in issues:
        status = {
            "version_mismatch": "version_mismatch",
            "duplicate": "duplicate",
            "not_found": "not_found",
            "reserved": "version_mismatch",
            "load_error": "error",
        }.get(issue.kind, "error")
        items.append(
            ExtensionInventoryItem(
                kind="analyzer",
                extension_id=issue.id,
                status=status,
                detail=issue.detail,
            )
        )

    # Installed but not enabled analyzers
    enabled_set = {item.strip() for item in (enabled_analyzers or ()) if item.strip()}
    for name, dist in _ep_names(ANALYZER_GROUP):
        # Best-effort: show EP name as disabled when not in allowlist
        if name not in enabled_set and not any(
            item.kind == "analyzer" and item.extension_id == name for item in items
        ):
            items.append(
                ExtensionInventoryItem(
                    kind="analyzer",
                    extension_id=name,
                    status="disabled",
                    detail=(
                        f"Installed ({dist or 'unknown'}) but not listed in "
                        "[extensions.analyzers].enabled"
                    ),
                )
            )

    return items


def inventory_to_jsonable(items: list[ExtensionInventoryItem]) -> list[dict[str, Any]]:
    """Serialize inventory rows for ``--json`` output."""

    return [
        {
            "kind": item.kind,
            "id": item.extension_id,
            "status": item.status,
            "detail": item.detail,
            "api_version": item.api_version,
        }
        for item in items
    ]


__all__ = [
    "ExtensionInventoryItem",
    "build_extension_inventory",
    "inventory_to_jsonable",
]
