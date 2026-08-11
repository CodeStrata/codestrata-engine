"""Runtime-behavior test: the execution package is unwired from the product path.

Importing any ``codestrata.ai.provider_contracts.execution_*`` /
``executor``/``timeout_policy``/``retry_policy``/``retry_decision``/``backoff``/
``error_classification`` module must not register anything, must not read the
environment or a file, and must not change the behavior of the existing
assess provider registry/factory or config settings resolution.

Slice 11.6 wired the executor for OpenAI only, so
``ai/providers/openai_provider.py`` and ``ai/provider_adapters/`` are no longer
part of the unwired product path here. Bedrock, the assessment/enrichment
services, doctor, config, and the CLI still are.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)

_EXECUTION_MODULES: tuple[str, ...] = (
    "codestrata.ai.provider_contracts.execution_policy",
    "codestrata.ai.provider_contracts.timeout_policy",
    "codestrata.ai.provider_contracts.backoff",
    "codestrata.ai.provider_contracts.retry_policy",
    "codestrata.ai.provider_contracts.retry_decision",
    "codestrata.ai.provider_contracts.error_classification",
    "codestrata.ai.provider_contracts.execution_models",
    "codestrata.ai.provider_contracts.executor",
    "codestrata.ai.provider_contracts.execution_diagnostics",
    "codestrata.ai.provider_contracts.execution_serialization",
    "codestrata.ai.provider_contracts.execution_compatibility",
)

_PRODUCT_PATH_FILES: tuple[str, ...] = (
    "src/codestrata/application/assessment/service.py",
    "src/codestrata/ai/enrichment/service.py",
    "src/codestrata/ai/providers/__init__.py",
    "src/codestrata/ai/providers/factory.py",
    "src/codestrata/ai/providers/doctor.py",
    "src/codestrata/ai/aws_config.py",
    "src/codestrata/extensions/assess_ai.py",
    "src/codestrata/config/settings.py",
    "src/codestrata/config/profiles.py",
    "src/codestrata/cli/assess.py",
)


def _engine_root() -> Path:
    # tests/ai/provider_contracts/test_execution_runtime_unwired.py -> engine/
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


def test_importing_execution_modules_does_not_touch_assess_registry() -> None:
    reset_assess_ai_provider_registry_for_tests()
    before = get_assess_ai_provider_registry().list_providers()

    for module_name in _EXECUTION_MODULES:
        importlib.import_module(module_name)

    reset_assess_ai_provider_registry_for_tests()
    after = get_assess_ai_provider_registry().list_providers()
    assert before == after == ("bedrock", "openai", "openrouter")
    reset_assess_ai_provider_registry_for_tests()


def test_no_product_path_file_imports_execution_modules() -> None:
    engine_root = _engine_root()
    offenders: dict[str, set[str]] = {}
    for relative in _PRODUCT_PATH_FILES:
        path = engine_root / relative
        if not path.is_file():
            continue
        imported = _imported_module_names(path)
        hits = {name for name in imported if name.startswith("codestrata.ai.provider_contracts")}
        if hits:
            offenders[relative] = hits
    assert offenders == {}, f"product path files import provider_contracts: {offenders}"


def test_execution_modules_define_no_module_level_side_effects() -> None:
    """None of the execution modules should define a process-wide singleton/default."""

    for module_name in _EXECUTION_MODULES:
        module = importlib.import_module(module_name)
        public_names = {name for name in dir(module) if not name.startswith("_")}
        assert not any("registry" in name.lower() for name in public_names)
        assert not any(name.lower().startswith("default_registry") for name in public_names)


def test_settings_module_is_unmodified_by_execution_package_existence() -> None:
    """Importing the execution package must not alter CodestrataSettings defaults."""

    from codestrata.config.settings import AiSettings

    for module_name in _EXECUTION_MODULES:
        importlib.import_module(module_name)

    settings = AiSettings()
    assert settings.provider == "bedrock"
    assert settings.openai.answer_model == "gpt-4o-mini"


def test_executor_module_imports_no_forbidden_runtime_or_sdk_dependencies() -> None:
    """executor.py must not import os/config/httpx/boto3/openai or provider concretes."""

    engine_root = _engine_root()
    path = engine_root / "src/codestrata/ai/provider_contracts/executor.py"
    imported = _imported_module_names(path)
    forbidden_prefixes = (
        "os",
        "boto3",
        "botocore",
        "httpx",
        "openai",
        "codestrata.config",
        "codestrata.ai.providers.bedrock",
        "codestrata.ai.providers.openai_provider",
        "codestrata.ai.providers.factory",
        "codestrata.ai.providers.doctor",
        "codestrata.extensions.assess_ai",
    )
    offenders = {
        name
        for name in imported
        for prefix in forbidden_prefixes
        if name == prefix or name.startswith(prefix + ".")
    }
    assert offenders == set(), f"executor.py imports forbidden dependencies: {offenders}"
