"""Dependency boundary: what the adapter may import, and where AWS may be reached."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from verification.bedrock_provider_migration.contract import (
    ALLOWED_INTERNAL_IMPORT_PREFIXES,
    AWS_CLIENT_FACTORY_NAME,
    AWS_CONFIG_IMPORTERS,
    AWS_CONFIG_PURE_HELPERS,
    CREDENTIAL_BOUNDARY_MODULE,
    EXPECTED_MODULES,
    FORBIDDEN_IMPORT_PREFIXES,
    FORBIDDEN_PROVIDER_TOKENS,
    FORBIDDEN_RUNTIME_IMPORT_MODULES,
    LEGACY_PATH_FILES,
    MIGRATED_PATH_FILES,
    SDK_FREE_PATH_FILES,
    SDK_MODULE_NAMES,
    WRAPPER_RELATIVE_PATH,
)
from verification.bedrock_provider_migration.inventory import imported_module_names, parse_module
from verification.bedrock_provider_migration.models import CheckResult

_CONTRACTS_PREFIX = "codestrata.ai.provider_contracts"
_AWS_CONFIG_MODULE = "codestrata.ai.aws_config"


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


def _imported_names_from(package_dir: Path, filename: str, module: str) -> set[str]:
    """Return the symbols imported via ``from <module> import ...``."""

    tree = parse_module(package_dir, filename)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


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
        name="bedrock_adapter_imports_no_forbidden_layer_or_the_openai_adapter",
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
        name="bedrock_adapter_internal_imports_stay_within_allowed_set",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={sorted(offenders)}",
        evidence={"allowed_prefixes": list(ALLOWED_INTERNAL_IMPORT_PREFIXES)},
    )


def check_only_client_imports_the_sdk(package_dir: Path) -> CheckResult:
    """``boto3``/``botocore`` may only be named by the credential boundary module."""

    importers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if any(
            name.split(".")[0] in set(SDK_MODULE_NAMES)
            for name in _imports_of(package_dir, filename)
        )
    )
    return CheckResult(
        name="only_the_client_module_imports_boto3_or_botocore",
        category="dependency_boundary",
        ok=importers in ([], [CREDENTIAL_BOUNDARY_MODULE]),
        detail=f"sdk_importers={importers}",
        evidence={"credential_boundary_module": CREDENTIAL_BOUNDARY_MODULE},
    )


def check_only_client_constructs_a_client(package_dir: Path) -> CheckResult:
    """Only ``client.py`` may call ``aws_config.create_bedrock_runtime_client``."""

    callers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if f"aws_config.{AWS_CLIENT_FACTORY_NAME}"
        in _attribute_accesses(package_dir, filename)
        or AWS_CLIENT_FACTORY_NAME
        in _imported_names_from(package_dir, filename, _AWS_CONFIG_MODULE)
    )
    return CheckResult(
        name="only_the_client_module_constructs_a_bedrock_runtime_client",
        category="dependency_boundary",
        ok=callers == [CREDENTIAL_BOUNDARY_MODULE],
        detail=f"client_factory_callers={callers}",
        evidence={"client_factory": AWS_CLIENT_FACTORY_NAME},
    )


def check_aws_config_is_imported_only_where_allowed(package_dir: Path) -> CheckResult:
    """``aws_config`` is reachable from the boundary and the bridge's pure formatter."""

    importers = sorted(
        filename
        for filename in _existing_modules(package_dir)
        if any(
            name == _AWS_CONFIG_MODULE or name.startswith(_AWS_CONFIG_MODULE + ".")
            or name == "codestrata.ai"
            for name in _imports_of(package_dir, filename)
        )
    )
    unexpected = sorted(set(importers) - set(AWS_CONFIG_IMPORTERS))
    bridge_symbols = _imported_names_from(
        package_dir, "legacy_bridge.py", _AWS_CONFIG_MODULE
    )
    bridge_is_pure = bridge_symbols <= set(AWS_CONFIG_PURE_HELPERS)
    return CheckResult(
        name="aws_config_is_reached_only_by_the_client_module_and_the_bridges_pure_formatter",
        category="dependency_boundary",
        ok=not unexpected and bridge_is_pure,
        detail=(
            f"unexpected_importers={unexpected} "
            f"legacy_bridge_symbols={sorted(bridge_symbols)}"
        ),
        evidence={
            "allowed_importers": list(AWS_CONFIG_IMPORTERS),
            "allowed_pure_helpers": list(AWS_CONFIG_PURE_HELPERS),
        },
    )


def check_no_module_reads_the_environment(package_dir: Path) -> CheckResult:
    """The adapter never reads ``os.environ``: AWS precedence belongs to ``aws_config``."""

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
    return CheckResult(
        name="no_bedrock_adapter_module_reads_the_environment_directly",
        category="dependency_boundary",
        ok=not importers and not readers,
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
        name="bedrock_adapter_imports_no_networking_threading_or_subprocess_module",
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
        name="bedrock_adapter_never_calls_time_sleep",
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
        name="bedrock_adapter_has_no_openrouter_references",
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
        name="migrated_bedrock_files_import_the_provider_contracts",
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
        name="orchestration_and_aws_config_still_do_not_import_the_provider_contracts",
        category="dependency_boundary",
        ok=not offenders,
        detail=f"offenders={offenders}",
        evidence={"legacy_files": list(LEGACY_PATH_FILES)},
    )


def check_orchestration_never_imports_the_sdk(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    offenders = [
        relative
        for relative in SDK_FREE_PATH_FILES
        if any(
            name.split(".")[0] in set(SDK_MODULE_NAMES)
            for name in _source_imports(src_root, relative)
        )
    ]
    return CheckResult(
        name="assessment_enrichment_cli_and_the_wrapper_never_import_boto3",
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


def check_the_wrapper_delegates_to_its_own_adapter(engine_root: Path) -> CheckResult:
    src_root = engine_root / "src" / "codestrata"
    names = _source_imports(src_root, WRAPPER_RELATIVE_PATH)
    uses_own_adapter = any(
        name.startswith("codestrata.ai.provider_adapters.bedrock") for name in names
    )
    borrows_openai = sorted(
        name
        for name in names
        if name.startswith("codestrata.ai.provider_adapters.openai")
        or name.startswith("codestrata.ai.providers.openai_provider")
    )
    return CheckResult(
        name="the_bedrock_wrapper_delegates_to_the_bedrock_adapter_and_never_the_openai_one",
        category="dependency_boundary",
        ok=uses_own_adapter and not borrows_openai,
        detail=f"uses_bedrock_adapter={uses_own_adapter} openai_imports={borrows_openai}",
    )


def run_dependency_boundary_checks(
    engine_root: Path, package_dir: Path
) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_no_forbidden_layer_imports(package_dir),
        check_internal_imports_stay_within_allowed_set(package_dir),
        check_only_client_imports_the_sdk(package_dir),
        check_only_client_constructs_a_client(package_dir),
        check_aws_config_is_imported_only_where_allowed(package_dir),
        check_no_module_reads_the_environment(package_dir),
        check_no_forbidden_runtime_imports(package_dir),
        check_adapter_never_sleeps(package_dir),
        check_no_openrouter_reference(package_dir),
        check_migrated_files_import_the_contracts(engine_root),
        check_legacy_files_do_not_import_the_contracts(engine_root),
        check_orchestration_never_imports_the_sdk(engine_root),
        check_provider_contracts_remain_sdk_free(engine_root),
        check_the_wrapper_delegates_to_its_own_adapter(engine_root),
    ]
    matrix: dict[str, Any] = {
        "allowed_internal_import_prefixes": list(ALLOWED_INTERNAL_IMPORT_PREFIXES),
        "aws_config_importers_allowed": list(AWS_CONFIG_IMPORTERS),
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
    "check_aws_config_is_imported_only_where_allowed",
    "check_internal_imports_stay_within_allowed_set",
    "check_legacy_files_do_not_import_the_contracts",
    "check_migrated_files_import_the_contracts",
    "check_no_forbidden_layer_imports",
    "check_no_forbidden_runtime_imports",
    "check_no_module_reads_the_environment",
    "check_no_openrouter_reference",
    "check_only_client_constructs_a_client",
    "check_only_client_imports_the_sdk",
    "check_orchestration_never_imports_the_sdk",
    "check_provider_contracts_remain_sdk_free",
    "check_the_wrapper_delegates_to_its_own_adapter",
    "run_dependency_boundary_checks",
]
