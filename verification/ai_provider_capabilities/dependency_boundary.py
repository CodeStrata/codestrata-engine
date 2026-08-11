"""Dependency boundary checks: SDK-free, environment-free, unwired capability/usage modules."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.ai_provider_capabilities.contract import (
    EXPECTED_MODULES,
    FORBIDDEN_ENVIRONMENT_IMPORT_MODULES,
    FORBIDDEN_IMPORT_PREFIXES,
    PRODUCT_PATH_FILES,
    SLICE_11_5_NEW_MODULES,
)
from verification.ai_provider_capabilities.models import CheckResult


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def check_no_forbidden_sdk_imports(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in EXPECTED_MODULES:
        imported = _imported_module_names(package_dir / filename)
        hits = sorted(
            name
            for name in imported
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            )
        )
        if hits:
            offenders[filename] = hits
    ok = not offenders
    return CheckResult(
        name="provider_contracts_has_no_forbidden_sdk_or_product_imports",
        category="dependency_boundary",
        ok=ok,
        detail=f"offenders={offenders}",
    )


def check_no_codestrata_imports_outside_package(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in EXPECTED_MODULES:
        imported = _imported_module_names(package_dir / filename)
        hits = sorted(
            name
            for name in imported
            if name.startswith("codestrata.")
            and not name.startswith("codestrata.ai.provider_contracts")
        )
        if hits:
            offenders[filename] = hits
    ok = not offenders
    return CheckResult(
        name="provider_contracts_has_no_codestrata_dependencies_outside_itself",
        category="dependency_boundary",
        ok=ok,
        detail=f"offenders={offenders}",
    )


def check_capability_and_usage_modules_never_import_forbidden_runtime_modules(
    package_dir: Path,
) -> CheckResult:
    """The 12 new capability_*/usage_* modules must never import os/pathlib/subprocess/etc."""

    offenders: dict[str, list[str]] = {}
    for filename in SLICE_11_5_NEW_MODULES:
        imported = _imported_module_names(package_dir / filename)
        hits = sorted(imported & set(FORBIDDEN_ENVIRONMENT_IMPORT_MODULES))
        if hits:
            offenders[filename] = hits
    ok = not offenders
    return CheckResult(
        name=(
            "capability_and_usage_modules_never_import_os_pathlib_subprocess_"
            "threading_asyncio_or_signal"
        ),
        category="dependency_boundary",
        ok=ok,
        detail=f"offenders={offenders}",
    )


def check_product_path_files_do_not_import_provider_contracts(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    offenders: list[str] = []
    for relative in PRODUCT_PATH_FILES:
        path = src_root / relative
        if not path.is_file():
            continue
        imported = _imported_module_names(path)
        if any(name.startswith("codestrata.ai.provider_contracts") for name in imported):
            offenders.append(relative)
    ok = not offenders
    return CheckResult(
        name="product_path_files_do_not_import_provider_contracts",
        category="dependency_boundary",
        ok=ok,
        detail=f"offenders={offenders}",
    )


_OPENROUTER_OPERATIONAL_WIRING_TOKENS: tuple[str, ...] = (
    "provider_adapters.openrouter",
    "OPENROUTER_API_KEY",
    "OpenRouterProvider",
)


def check_no_openrouter_references(package_dir: Path) -> CheckResult:
    """Contracts may name ProviderId.OPENROUTER; they must stay adapter-free."""

    hits: list[str] = []
    for filename in EXPECTED_MODULES:
        path = package_dir / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in _OPENROUTER_OPERATIONAL_WIRING_TOKENS):
            hits.append(filename)
    ok = not hits
    return CheckResult(
        name="provider_contracts_has_no_openrouter_adapter_or_api_key_wiring",
        category="dependency_boundary",
        ok=ok,
        detail=f"hits={sorted(hits)}",
    )


def check_ai_providers_directory_unchanged(engine_root: Path) -> CheckResult:
    """The pre-existing ``ai/providers/`` file set must remain untouched by Slice 11.5."""

    from verification.ai_provider_baseline.contract import ALLOWED_AI_PROVIDERS_DIRECTORY_FILES

    providers_dir = engine_root / "src" / "codestrata" / "ai" / "providers"
    actual = {p.name for p in providers_dir.iterdir() if p.is_file() and p.suffix == ".py"}
    unexpected = sorted(actual - ALLOWED_AI_PROVIDERS_DIRECTORY_FILES)
    ok = not unexpected
    return CheckResult(
        name="ai_providers_directory_has_no_new_files_from_slice_11_5",
        category="dependency_boundary",
        ok=ok,
        detail=f"unexpected={unexpected}",
    )


def run_dependency_boundary_checks(
    engine_root: Path, package_dir: Path
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_no_forbidden_sdk_imports(package_dir),
        check_no_codestrata_imports_outside_package(package_dir),
        check_capability_and_usage_modules_never_import_forbidden_runtime_modules(package_dir),
        check_product_path_files_do_not_import_provider_contracts(engine_root),
        check_no_openrouter_references(package_dir),
        check_ai_providers_directory_unchanged(engine_root),
    ]
    matrix = {
        "forbidden_import_prefixes": list(FORBIDDEN_IMPORT_PREFIXES),
        "product_path_files_checked": list(PRODUCT_PATH_FILES),
    }
    return checks, matrix


__all__ = [
    "check_ai_providers_directory_unchanged",
    "check_capability_and_usage_modules_never_import_forbidden_runtime_modules",
    "check_no_codestrata_imports_outside_package",
    "check_no_forbidden_sdk_imports",
    "check_no_openrouter_references",
    "check_product_path_files_do_not_import_provider_contracts",
    "run_dependency_boundary_checks",
]
