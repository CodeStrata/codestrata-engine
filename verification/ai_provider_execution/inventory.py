"""Structural inventory of ``codestrata.ai.provider_contracts`` after Slice 11.4.

Uses :mod:`ast` only (never ``exec``/dynamic import of arbitrary paths) to
record classes, functions, and imports for each module. Output uses dotted
module names only — never absolute filesystem paths.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.ai_provider_execution.contract import (
    EXPECTED_MODULES,
    PACKAGE_RELATIVE_PATH,
    SLICE_11_4_NEW_MODULES,
)
from verification.ai_provider_execution.models import CheckResult


def _class_names(tree: ast.Module) -> list[str]:
    return sorted(
        node.name for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)
    )


def _function_names(tree: ast.Module) -> list[str]:
    return sorted(
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    )


def _imported_module_names(tree: ast.Module) -> list[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return sorted(names)


def inspect_module(package_dir: Path, filename: str) -> dict[str, Any]:
    file_path = package_dir / filename
    text = file_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=filename)
    dotted_module = f"codestrata.ai.provider_contracts.{filename[: -len('.py')]}"
    return {
        "classes": _class_names(tree),
        "functions": _function_names(tree),
        "imports": _imported_module_names(tree),
        "line_count": len(text.splitlines()),
        "module": dotted_module,
    }


def build_package_inventory(package_dir: Path) -> tuple[dict[str, Any], ...]:
    entries = [inspect_module(package_dir, name) for name in EXPECTED_MODULES]
    return tuple(sorted(entries, key=lambda entry: entry["module"]))


def check_expected_modules_present(package_dir: Path) -> CheckResult:
    actual = {p.name for p in package_dir.iterdir() if p.is_file() and p.suffix == ".py"}
    expected = set(EXPECTED_MODULES)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    ok = not missing and not unexpected
    return CheckResult(
        name="provider_contracts_package_has_exactly_expected_modules_after_slice_11_4",
        category="inventory",
        ok=ok,
        detail=f"missing={missing} unexpected={unexpected}",
        evidence={"expected_count": len(expected), "actual_count": len(actual)},
    )


def check_slice_11_4_new_modules_present(package_dir: Path) -> CheckResult:
    actual = {p.name for p in package_dir.iterdir() if p.is_file() and p.suffix == ".py"}
    missing = sorted(set(SLICE_11_4_NEW_MODULES) - actual)
    ok = not missing
    return CheckResult(
        name="all_eleven_slice_11_4_execution_modules_are_present",
        category="inventory",
        ok=ok,
        detail=f"missing={missing}",
        evidence={"expected_count": len(SLICE_11_4_NEW_MODULES)},
    )


def check_package_relative_path(engine_root: Path) -> CheckResult:
    package_dir = engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH
    ok = package_dir.is_dir()
    return CheckResult(
        name="provider_contracts_package_exists_at_documented_sibling_location",
        category="inventory",
        ok=ok,
        detail=f"expected directory src/codestrata/{PACKAGE_RELATIVE_PATH}",
    )


def run_inventory_checks(
    engine_root: Path, package_dir: Path
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_package_relative_path(engine_root),
        check_expected_modules_present(package_dir),
        check_slice_11_4_new_modules_present(package_dir),
    ]
    matrix: dict[str, Any] = {"modules": list(build_package_inventory(package_dir))}
    return checks, matrix


__all__ = [
    "build_package_inventory",
    "check_expected_modules_present",
    "check_package_relative_path",
    "check_slice_11_4_new_modules_present",
    "inspect_module",
    "run_inventory_checks",
]
