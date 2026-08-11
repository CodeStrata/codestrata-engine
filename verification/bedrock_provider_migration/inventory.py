"""Structural inventory of ``codestrata.ai.provider_adapters.bedrock``.

Uses :mod:`ast` only. Output records dotted module names, never absolute
filesystem paths.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.bedrock_provider_migration.contract import (
    ADAPTERS_ROOT_RELATIVE_PATH,
    EXPECTED_MODULES,
    PACKAGE_DOTTED_NAME,
    PACKAGE_RELATIVE_PATH,
)
from verification.bedrock_provider_migration.models import CheckResult


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


def imported_module_names(tree: ast.Module) -> list[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return sorted(names)


def parse_module(package_dir: Path, filename: str) -> ast.Module:
    path = package_dir / filename
    return ast.parse(path.read_text(encoding="utf-8"), filename=filename)


def inspect_module(package_dir: Path, filename: str) -> dict[str, Any]:
    path = package_dir / filename
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=filename)
    stem = filename[: -len(".py")]
    dotted = PACKAGE_DOTTED_NAME if stem == "__init__" else f"{PACKAGE_DOTTED_NAME}.{stem}"
    return {
        "classes": _class_names(tree),
        "functions": _function_names(tree),
        "imports": imported_module_names(tree),
        "line_count": len(text.splitlines()),
        "module": dotted,
    }


def build_package_inventory(package_dir: Path) -> tuple[dict[str, Any], ...]:
    entries = [
        inspect_module(package_dir, name)
        for name in EXPECTED_MODULES
        if (package_dir / name).is_file()
    ]
    return tuple(sorted(entries, key=lambda entry: entry["module"]))


def check_package_exists(engine_root: Path) -> CheckResult:
    package_dir = engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH
    return CheckResult(
        name="bedrock_adapter_package_exists_at_documented_location",
        category="inventory",
        ok=package_dir.is_dir(),
        detail=f"expected directory src/codestrata/{PACKAGE_RELATIVE_PATH}",
    )


def check_adapters_root_is_a_package(engine_root: Path) -> CheckResult:
    init_path = (
        engine_root / "src" / "codestrata" / ADAPTERS_ROOT_RELATIVE_PATH / "__init__.py"
    )
    return CheckResult(
        name="provider_adapters_root_is_an_importable_package",
        category="inventory",
        ok=init_path.is_file(),
        detail=f"expected src/codestrata/{ADAPTERS_ROOT_RELATIVE_PATH}/__init__.py",
    )


def check_expected_modules_present(package_dir: Path) -> CheckResult:
    actual = {
        path.name
        for path in package_dir.iterdir()
        if path.is_file() and path.suffix == ".py"
    }
    expected = set(EXPECTED_MODULES)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    return CheckResult(
        name="bedrock_adapter_package_has_exactly_expected_modules",
        category="inventory",
        ok=not missing and not unexpected,
        detail=f"missing={missing} unexpected={unexpected}",
        evidence={"actual_count": len(actual), "expected_count": len(expected)},
    )


def check_the_package_mirrors_the_openai_layout(engine_root: Path) -> CheckResult:
    """Approach A: the Bedrock package has the same module names as OpenAI's."""

    openai_dir = engine_root / "src" / "codestrata" / ADAPTERS_ROOT_RELATIVE_PATH / "openai"
    bedrock_dir = engine_root / "src" / "codestrata" / PACKAGE_RELATIVE_PATH
    openai_modules = sorted(
        path.name for path in openai_dir.glob("*.py") if path.is_file()
    )
    bedrock_modules = sorted(
        path.name for path in bedrock_dir.glob("*.py") if path.is_file()
    )
    return CheckResult(
        name="the_bedrock_package_mirrors_the_openai_module_layout",
        category="inventory",
        ok=openai_modules == bedrock_modules,
        detail=f"openai_only={sorted(set(openai_modules) - set(bedrock_modules))} "
        f"bedrock_only={sorted(set(bedrock_modules) - set(openai_modules))}",
        evidence={"module_count": len(bedrock_modules)},
    )


def check_every_module_is_documented(package_dir: Path) -> CheckResult:
    undocumented: list[str] = []
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        if not ast.get_docstring(tree):
            undocumented.append(filename)
    return CheckResult(
        name="every_bedrock_adapter_module_has_a_module_docstring",
        category="inventory",
        ok=not undocumented,
        detail=f"undocumented={undocumented}",
    )


def check_every_module_declares_all(package_dir: Path) -> CheckResult:
    missing: list[str] = []
    for filename in EXPECTED_MODULES:
        if filename == "__init__.py":
            continue
        path = package_dir / filename
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
        declares = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
            )
            for node in ast.iter_child_nodes(tree)
        )
        if not declares:
            missing.append(filename)
    return CheckResult(
        name="every_bedrock_adapter_module_declares_an_explicit_public_surface",
        category="inventory",
        ok=not missing,
        detail=f"missing___all__={missing}",
    )


def run_inventory_checks(
    engine_root: Path, package_dir: Path
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_package_exists(engine_root),
        check_adapters_root_is_a_package(engine_root),
        check_expected_modules_present(package_dir),
        check_the_package_mirrors_the_openai_layout(engine_root),
        check_every_module_is_documented(package_dir),
        check_every_module_declares_all(package_dir),
    ]
    matrix: dict[str, Any] = {
        "expected_module_count": len(EXPECTED_MODULES),
        "modules": list(build_package_inventory(package_dir)),
    }
    return checks, matrix


__all__ = [
    "build_package_inventory",
    "check_adapters_root_is_a_package",
    "check_every_module_declares_all",
    "check_every_module_is_documented",
    "check_expected_modules_present",
    "check_package_exists",
    "check_the_package_mirrors_the_openai_layout",
    "imported_module_names",
    "inspect_module",
    "parse_module",
    "run_inventory_checks",
]
