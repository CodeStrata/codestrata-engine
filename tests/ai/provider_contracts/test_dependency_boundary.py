"""Architecture test: provider_contracts must stay SDK-free and unwired.

Two directions are checked:

1. Nothing under ``codestrata.ai.provider_contracts`` imports a forbidden
   SDK/product module (openai, boto3, botocore, httpx, requests, platform,
   datalake, telemetry, analytics, cli, reporting).
2. Nothing on the *legacy* product path (assessment/enrichment service,
   providers/__init__.py, providers/factory.py, extensions/assess_ai.py)
   imports ``codestrata.ai.provider_contracts``.

Slice 11.6 migrated OpenAI and Slice 11.7 migrated Bedrock onto the
contracts, so ``provider_adapters/`` and the ``openai_provider.py`` /
``bedrock.py`` compatibility wrappers are expected to import them. The
orchestration layers stay on the legacy path.
"""

from __future__ import annotations

import ast
from pathlib import Path

import codestrata.ai.provider_contracts as provider_contracts_package

_FORBIDDEN_MODULE_PREFIXES: tuple[str, ...] = (
    "openai",
    "boto3",
    "botocore",
    "httpx",
    "requests",
    "codestrata.platform",
    "codestrata.datalake",
    "codestrata.telemetry",
    "codestrata.analytics",
    "codestrata.cli",
    "codestrata.reporting",
)

_PRODUCT_PATH_FILES: tuple[str, ...] = (
    "src/codestrata/application/assessment/service.py",
    "src/codestrata/ai/enrichment/service.py",
    "src/codestrata/ai/providers/__init__.py",
    "src/codestrata/ai/providers/factory.py",
    "src/codestrata/extensions/assess_ai.py",
)

_MIGRATED_PATH_PREFIXES: tuple[str, ...] = (
    "ai/provider_adapters/",
    "ai/providers/openai_provider.py",
    "ai/providers/bedrock.py",
)


def _package_dir() -> Path:
    return Path(provider_contracts_package.__file__).resolve().parent


def _engine_root() -> Path:
    # tests/ai/provider_contracts/test_dependency_boundary.py -> parents[3] == engine/
    return Path(__file__).resolve().parents[3]


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_provider_contracts_package_has_no_forbidden_imports() -> None:
    package_dir = _package_dir()
    offenders: dict[str, set[str]] = {}
    for path in sorted(package_dir.glob("*.py")):
        imported = _imported_module_names(path)
        hits = {
            name
            for name in imported
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in _FORBIDDEN_MODULE_PREFIXES
            )
        }
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, f"forbidden imports found: {offenders}"


def test_provider_contracts_package_has_no_codestrata_dependencies_outside_itself() -> None:
    """Every internal import must stay within codestrata.ai.provider_contracts."""

    package_dir = _package_dir()
    offenders: dict[str, set[str]] = {}
    for path in sorted(package_dir.glob("*.py")):
        imported = _imported_module_names(path)
        hits = {
            name
            for name in imported
            if name.startswith("codestrata.")
            and not name.startswith("codestrata.ai.provider_contracts")
        }
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, f"unexpected codestrata dependencies found: {offenders}"


def test_product_path_files_do_not_import_provider_contracts() -> None:
    engine_root = _engine_root()
    offenders: list[str] = []
    for relative in _PRODUCT_PATH_FILES:
        path = engine_root / relative
        if not path.is_file():
            continue
        imported = _imported_module_names(path)
        if any(name.startswith("codestrata.ai.provider_contracts") for name in imported):
            offenders.append(relative)
    assert offenders == [], f"product path files import provider_contracts: {offenders}"


def test_no_file_under_ai_or_extensions_imports_provider_contracts_except_new_package() -> None:
    engine_root = _engine_root()
    src_root = engine_root / "src" / "codestrata"
    offenders: list[str] = []
    for path in sorted((src_root / "ai").rglob("*.py")):
        if "provider_contracts" in path.parts:
            continue
        relative = str(path.relative_to(src_root))
        if relative.startswith(_MIGRATED_PATH_PREFIXES):
            continue
        imported = _imported_module_names(path)
        if any(name.startswith("codestrata.ai.provider_contracts") for name in imported):
            offenders.append(relative)
    extensions_ai = src_root / "extensions" / "assess_ai.py"
    if extensions_ai.is_file():
        imported = _imported_module_names(extensions_ai)
        if any(name.startswith("codestrata.ai.provider_contracts") for name in imported):
            offenders.append(str(extensions_ai.relative_to(src_root)))
    assert offenders == [], f"unexpected provider_contracts imports found in: {offenders}"


def test_migrated_openai_path_does_import_provider_contracts() -> None:
    """The Slice 11.6 OpenAI path is wired: it must depend on the contracts."""

    src_root = _engine_root() / "src" / "codestrata"
    expected = (
        src_root / "ai" / "provider_adapters" / "openai" / "adapter.py",
        src_root / "ai" / "providers" / "openai_provider.py",
    )
    unwired: list[str] = []
    for path in expected:
        imported = _imported_module_names(path)
        if not any(name.startswith("codestrata.ai.provider_contracts") for name in imported):
            unwired.append(str(path.relative_to(src_root)))
    assert unwired == [], f"migrated OpenAI files do not import provider_contracts: {unwired}"
