"""Render the E02.1 call-path inventory as Markdown."""

from __future__ import annotations

from verification.call_path_inventory.models import CallPathInventory


def render_inventory(inventory: CallPathInventory) -> str:
    factory = inventory.factory
    deps = inventory.dependencies
    snap = inventory.snapshots
    lines: list[str] = [
        "# E02.1 — Active SQLite, hosted and portfolio call paths",
        "",
        "Read-only inventory of **current** Engine composition after E02.3 "
        "Community surface narrowing. Platform and `workers/` trees were "
        "scanned, not edited.",
        "",
        "## Factory runtime composition",
        "",
        f"- Module: `{factory.module}`",
        f"- `create_knowledge_store()` constructs **`{factory.constructs_class}`**",
        f"- Source imports `SqliteKnowledgeStore`: `{factory.source_imports_sqlite_store}`",
        f"- Annotated return type: `{factory.return_annotation}`",
        "",
        "Imports alone are not the evidence. The factory's runtime return type is.",
        "",
        "## Default package dependency closure",
        "",
    ]
    for item in deps.default:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            f"- `sqlite3` is stdlib: `{deps.sqlite3_is_stdlib}` (not declared in pyproject)",
            f"- `mcp` optional extra present: `{deps.mcp_is_optional_extra}`",
            f"- Forbidden DB/hosted drivers in default extras: "
            f"`{', '.join(deps.forbidden_in_default) or '(none)'}`",
            "",
            "## Persisted snapshot layout (current)",
            "",
            f"- Knowledge directory: `{snap.knowledge_directory}`",
            f"- Database file: `{snap.database_filename}` (schema v{snap.schema_version})",
            f"- Blob kinds: {', '.join(f'`{kind}`' for kind in snap.blob_kinds)}",
            "",
        ]
    )
    for note in snap.layout_notes:
        lines.append(f"- {note}")
    lines.extend(["", "## Composition call sites", ""])
    for call in inventory.composition_calls:
        names = ", ".join(f"`{name}`" for name in call.names)
        lines.append(f"- `{call.relative_path}` — {names}")
    lines.extend(["", "## Production `sqlite3` imports", ""])
    for path in inventory.sqlite3_production_modules:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Hosted / Platform ingest markers", ""])
    for path in inventory.hosted_modules:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Portfolio / EIR markers", ""])
    for path in inventory.portfolio_modules:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Outside-Engine consumers (read-only)",
            "",
            "Recorded **before** any later interface narrowing. Do not copy Engine",
            "code into `platform/` or `workers/` to satisfy these imports.",
            "",
            f"- vscode-plugin Python `codestrata` imports: "
            f"`{inventory.vscode_python_codestrata_imports}`",
            f"- workers Python `codestrata` imports: `{inventory.workers_codestrata_imports}`",
            "",
        ]
    )
    if not inventory.platform_consumers:
        lines.append("- (no matching Platform/verification/infrastructure imports)")
    else:
        for hit in inventory.platform_consumers:
            lines.append(
                f"- `{hit.relative_path}:{hit.lineno}` → `{hit.module}` ({hit.consumer_root})"
            )
    lines.extend(["", "## Classification", ""])
    lines.append("| ID | Class | In runtime | In default closure | Summary |")
    lines.append("|---|---|---|---|---|")
    for surface in inventory.surfaces:
        runtime = "yes" if surface.in_supported_runtime else "no"
        closure = "yes" if surface.in_default_dependency_closure else "no"
        summary = surface.summary.replace("|", "/")
        lines.append(
            f"| `{surface.id}` | {surface.classification} | {runtime} | {closure} | {summary} |"
        )
    lines.extend(
        [
            "",
            "### Classification rules used",
            "",
            "- **retain** — local YAML/file Engine ports, optional MCP extra,",
            "  always-offline Platform client, maintainer SQLite export helper.",
            "- **adapt** — on the supported runtime today (CLI/MCP composition).",
            "- **deprecate** — still loaded with every settings parse (pgvector",
            "  setting) but has no Engine adapter.",
            "- **quarantine** — absent from Community runtime composition. SQLite",
            "  adapter, hosted ingest, and portfolio lifecycle are not executed.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"
