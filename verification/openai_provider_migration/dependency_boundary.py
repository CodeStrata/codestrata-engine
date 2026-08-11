"""Dependency boundary: what the adapter may import, and where credentials may be read."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.openai_provider_migration.contract import (
    ALLOWED_INTERNAL_IMPORT_PREFIXES,
    CREDENTIAL_BOUNDARY_MODULE,
    EXPECTED_MODULES,
    FORBIDDEN_IMPORT_PREFIXES,
    FORBIDDEN_PROVIDER_TOKENS,
    FORBIDDEN_RUNTIME_IMPORT_MODULES,
    LEGACY_PATH_FILES,
    MIGRATED_PATH_FILES,
    SDK_FREE_PATH_FILES,
)
from verification.openai_provider_migration.inventory import imported_module_names, parse_module
from verification.openai_provider_migration.models import CheckResult

_CONTRACTS_PREFIX = "codestrata.ai.provider_contracts"


def _existing_modules(package_dir: Path) -> list[str]:
    return [name for name in EXPECTED_MODULES if (package_dir / name).is_file()]


def _imports_of(package_dir: Path, filename: str) -> list[str]:
    return imported_module_names(parse_module(package_dir, filename))


def _attribute_accesses(package_dir: Path, filename: str) -> set[str]:
    """Return ``name.attribute`` pairs used in code, so prose never trips a check."""

    tree = parse_module(package_dir, filename)
    accesses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            accesses.add(f"{node.value.id}.{node.attr}")
    return accesses


def check_no_forbidden_layer_imports(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in _existing_modules(package_dir):
        hits = sorted(
            name
            for name in _imports_of(package_dir, filename)
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            )
        )
        if hits:
            offenders[filename] = hits
    return CheckResult(
        name="openai_adapter_imports_no_forbidden_layer",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
        evidence={"forbidden_prefixes": list(FORBIDDEN_IMPORT_PREFIXES)},
    )


def check_internal_imports_stay_within_allowed_set(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in _existing_modules(package_dir):
        hits = sorted(
            name
            for name in _imports_of(package_dir, filename)
            if name.startswith("codestrata.")
            and not name.startswith(ALLOWED_INTERNAL_IMPORT_PREFIXES)
        )
        if hits:
            offenders[filename] = hits
    return CheckResult(
        name="openai_adapter_internal_imports_stay_within_allowed_set",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
        evidence={"allowed_prefixes": list(ALLOWED_INTERNAL_IMPORT_PREFIXES)},
    )


def check_only_client_imports_the_sdk(package_dir: Path) -> CheckResult:
    importers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if any(
            name == "openai" or name.startswith("openai.")
            for name in _imports_of(package_dir, filename)
        )
    )
    return CheckResult(
        name="only_the_client_module_imports_the_openai_sdk",
        category="dependency_boundary",
        ok=importers == [CREDENTIAL_BOUNDARY_MODULE],
        detail=f"sdk_importers={importers}",
        evidence={"credential_boundary_module": CREDENTIAL_BOUNDARY_MODULE},
    )


def check_only_client_reads_the_environment(package_dir: Path) -> CheckResult:
    importers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if "os" in _imports_of(package_dir, filename)
    )
    readers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if {"os.environ", "os.getenv"} & _attribute_accesses(package_dir, filename)
    )
    ok = importers == [CREDENTIAL_BOUNDARY_MODULE] and readers == [CREDENTIAL_BOUNDARY_MODULE]
    return CheckResult(
        name="only_the_client_module_reads_the_environment",
        category="dependency_boundary",
        ok=ok,
        detail=f"os_importers={importers} environment_readers={readers}",
    )


def check_no_forbidden_runtime_imports(package_dir: Path) -> CheckResult:
    offenders: dict[str, list[str]] = {}
    for filename in _existing_modules(package_dir):
        hits = sorted(
            name
            for name in _imports_of(package_dir, filename)
            if name.split(".")[0] in set(FORBIDDEN_RUNTIME_IMPORT_MODULES)
        )
        if hits:
            offenders[filename] = hits
    return CheckResult(
        name="openai_adapter_imports_no_networking_threading_or_subprocess_module",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
        evidence={"forbidden_modules": list(FORBIDDEN_RUNTIME_IMPORT_MODULES)},
    )


def check_adapter_never_sleeps(package_dir: Path) -> CheckResult:
    offenders = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if "time.sleep" in _attribute_accesses(package_dir, filename)
    )
    return CheckResult(
        name="openai_adapter_never_calls_time_sleep",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_no_openrouter_reference(package_dir: Path) -> CheckResult:
    offenders: list[str] = []
    for filename in _existing_modules(package_dir):
        text = (package_dir / filename).read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN_PROVIDER_TOKENS):
            offenders.append(filename)
    return CheckResult(
        name="openai_adapter_has_no_openrouter_references",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
    )


def _source_imports(src_root: Path, relative: str) -> set[str]:
    path = src_root / relative
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    return set(imported_module_names(tree))


def check_migrated_files_import_the_contracts(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    unwired = [
        relative
        for relative in MIGRATED_PATH_FILES
        if not any(
            name.startswith(_CONTRACTS_PREFIX) for name in _source_imports(src_root, relative)
        )
    ]
    return CheckResult(
        name="migrated_openai_files_import_the_provider_contracts",
        category="dependency_boundary",
        ok=not unwired,
        detail=f"unwired={unwired}",
        evidence={"migrated_files": list(MIGRATED_PATH_FILES)},
    )


def check_legacy_files_do_not_import_the_contracts(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    offenders = [
        relative
        for relative in LEGACY_PATH_FILES
        if any(name.startswith(_CONTRACTS_PREFIX) for name in _source_imports(src_root, relative))
    ]
    return CheckResult(
        name="legacy_path_files_still_do_not_import_the_provider_contracts",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
        evidence={"legacy_files": list(LEGACY_PATH_FILES)},
    )


def check_assessment_and_enrichment_never_import_the_sdk(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    offenders = [
        relative
        for relative in SDK_FREE_PATH_FILES
        if any(
            name == "openai" or name.startswith("openai.")
            for name in _source_imports(src_root, relative)
        )
    ]
    return CheckResult(
        name="assessment_enrichment_and_cli_never_import_the_openai_sdk",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
        evidence={"sdk_free_files": list(SDK_FREE_PATH_FILES)},
    )


def check_provider_contracts_remain_sdk_free(engine_root: Path) -> CheckResult:
    contracts_dir = engine_root / "src" / "codestrata" / "ai" / "provider_contracts"
    offenders: list[str] = []
    for path in sorted(contracts_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        names = set(imported_module_names(tree))
        if any(
            name.split(".")[0] in {"openai", "boto3", "botocore", "httpx"} for name in names
        ) or any(name.startswith("codestrata.ai.provider_adapters") for name in names):
            offenders.append(path.name)
    return CheckResult(
        name="provider_contracts_remain_sdk_free_and_adapter_agnostic",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def check_wrapper_does_not_import_the_sdk(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    names = _source_imports(src_root, "ai/providers/openai_provider.py")
    offenders = sorted(
        name for name in names if name == "openai" or name.startswith("openai.")
    )
    return CheckResult(
        name="openai_provider_wrapper_does_not_import_the_openai_sdk",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
    )


def run_dependency_boundary_checks(
    engine_root: Path, package_dir: Path
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_no_forbidden_layer_imports(package_dir),
        check_internal_imports_stay_within_allowed_set(package_dir),
        check_only_client_imports_the_sdk(package_dir),
        check_only_client_reads_the_environment(package_dir),
        check_no_forbidden_runtime_imports(package_dir),
        check_adapter_never_sleeps(package_dir),
        check_no_openrouter_reference(package_dir),
        check_migrated_files_import_the_contracts(engine_root),
        check_legacy_files_do_not_import_the_contracts(engine_root),
        check_assessment_and_enrichment_never_import_the_sdk(engine_root),
        check_provider_contracts_remain_sdk_free(engine_root),
        check_wrapper_does_not_import_the_sdk(engine_root),
    ]
    matrix: dict[str, Any] = {
        "allowed_internal_import_prefixes": list(ALLOWED_INTERNAL_IMPORT_PREFIXES),
        "credential_boundary_module": CREDENTIAL_BOUNDARY_MODULE,
        "forbidden_import_prefixes": list(FORBIDDEN_IMPORT_PREFIXES),
        "forbidden_runtime_import_modules": list(FORBIDDEN_RUNTIME_IMPORT_MODULES),
        "legacy_path_files_checked": list(LEGACY_PATH_FILES),
        "migrated_path_files_checked": list(MIGRATED_PATH_FILES),
        "sdk_free_path_files_checked": list(SDK_FREE_PATH_FILES),
    }
    return checks, matrix


__all__ = [
    "check_adapter_never_sleeps",
    "check_assessment_and_enrichment_never_import_the_sdk",
    "check_internal_imports_stay_within_allowed_set",
    "check_legacy_files_do_not_import_the_contracts",
    "check_migrated_files_import_the_contracts",
    "check_no_forbidden_layer_imports",
    "check_no_forbidden_runtime_imports",
    "check_no_openrouter_reference",
    "check_only_client_imports_the_sdk",
    "check_only_client_reads_the_environment",
    "check_provider_contracts_remain_sdk_free",
    "check_wrapper_does_not_import_the_sdk",
    "run_dependency_boundary_checks",
]
