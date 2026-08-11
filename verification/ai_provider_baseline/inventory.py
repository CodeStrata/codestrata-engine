"""Structural coupling inventory of the existing AI provider surface.

Uses :mod:`ast` (never ``exec``/``import`` of arbitrary code paths) to record
classes, functions, and internal (``codestrata.*``) imports for each
inventoried module. Output uses relative module names only — never absolute
filesystem paths — so the report is safe to share and diff across machines.
"""

from __future__ import annotations

import ast
from pathlib import Path

from verification.ai_provider_baseline.contract import INVENTORIED_MODULES
from verification.ai_provider_baseline.models import CouplingInventoryEntry


def _class_info(node: ast.ClassDef) -> dict[str, object]:
    bases: list[str] = []
    for base in node.bases:
        bases.append(ast.unparse(base))
    methods = sorted(
        item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return {"bases": sorted(bases), "methods": methods, "name": node.name}


def _internal_imports(tree: ast.Module) -> list[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("codestrata"):
                imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("codestrata"):
                    imports.add(alias.name)
    return sorted(imports)


def inspect_module(source_root: Path, relative_path: str) -> CouplingInventoryEntry:
    """Parse one module and return its structural coupling entry.

    ``relative_path`` is relative to ``src/codestrata`` (e.g.
    ``ai/providers/bedrock.py``); the returned entry's ``module`` field is
    the dotted equivalent (``ai.providers.bedrock``).
    """

    file_path = source_root / relative_path
    text = file_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=relative_path)

    classes = tuple(
        _class_info(node) for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)
    )
    functions = tuple(
        sorted(
            node.name
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        )
    )
    dotted_module = relative_path[: -len(".py")].replace("/", ".")
    return CouplingInventoryEntry(
        module=dotted_module,
        classes=classes,
        functions=functions,
        internal_imports=tuple(_internal_imports(tree)),
        line_count=len(text.splitlines()),
    )


def build_coupling_inventory(source_root: Path) -> tuple[CouplingInventoryEntry, ...]:
    """Build the deterministic (sorted by module) coupling inventory."""

    entries = [inspect_module(source_root, relative) for relative in INVENTORIED_MODULES]
    return tuple(sorted(entries, key=lambda entry: entry.module))


def find_settings_classes(
    source_root: Path,
    *,
    class_names: tuple[str, ...] = (
        "AiSettings",
        "BedrockSettings",
        "OpenAISettings",
        "AwsSettings",
    ),
) -> tuple[dict[str, object], ...]:
    """Extract field-level structure for the AI-relevant settings classes.

    Reads ``config/settings.py`` with :mod:`ast` only; never imports Pydantic
    models in order to keep this purely structural (no dynamic defaults such
    as environment reads are evaluated).
    """

    file_path = source_root / "config" / "settings.py"
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename="config/settings.py")

    results: list[dict[str, object]] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef) or node.name not in class_names:
            continue
        fields: list[dict[str, object]] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(
                    {
                        "annotation": ast.unparse(item.annotation),
                        "has_default": item.value is not None,
                        "name": item.target.id,
                    }
                )
        results.append({"class_name": node.name, "fields": sorted(fields, key=lambda f: f["name"])})
    return tuple(sorted(results, key=lambda r: r["class_name"]))


__all__ = [
    "build_coupling_inventory",
    "find_settings_classes",
    "inspect_module",
]
