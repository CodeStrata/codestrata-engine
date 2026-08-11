"""Runtime-behavior test: capability/usage modules are unwired from the product path.

Importing any ``codestrata.ai.provider_contracts.capability_*``/``usage_*``
module (including the in-place-extended ``usage.py``) must not register
anything, must not read the environment or a file, and must not change the
behavior of the existing assess provider registry/factory or config
settings resolution.

Slice 11.6 wired these modules for OpenAI only, so
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

_CAPABILITY_MODULES: tuple[str, ...] = (
    "codestrata.ai.provider_contracts.capability_policy",
    "codestrata.ai.provider_contracts.capability_schema",
    "codestrata.ai.provider_contracts.capability_models",
    "codestrata.ai.provider_contracts.capability_catalogs",
    "codestrata.ai.provider_contracts.capability_validation",
    "codestrata.ai.provider_contracts.capability_serialization",
    "codestrata.ai.provider_contracts.capability_diagnostics",
    "codestrata.ai.provider_contracts.capability_compatibility",
    "codestrata.ai.provider_contracts.usage_policy",
    "codestrata.ai.provider_contracts.usage",
    "codestrata.ai.provider_contracts.usage_validation",
    "codestrata.ai.provider_contracts.usage_serialization",
    "codestrata.ai.provider_contracts.usage_diagnostics",
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
    # tests/ai/provider_contracts/test_capability_runtime_unwired.py -> engine/
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


def test_importing_capability_modules_does_not_touch_assess_registry() -> None:
    reset_assess_ai_provider_registry_for_tests()
    before = get_assess_ai_provider_registry().list_providers()

    for module_name in _CAPABILITY_MODULES:
        importlib.import_module(module_name)

    reset_assess_ai_provider_registry_for_tests()
    after = get_assess_ai_provider_registry().list_providers()
    assert before == after == ("bedrock", "openai", "openrouter")
    reset_assess_ai_provider_registry_for_tests()


def test_no_product_path_file_imports_capability_modules() -> None:
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


def test_capability_modules_define_no_module_level_registry_or_singleton() -> None:
    """None of the capability/usage modules should define a process-wide singleton/registry."""

    for module_name in _CAPABILITY_MODULES:
        module = importlib.import_module(module_name)
        public_names = {name for name in dir(module) if not name.startswith("_")}
        assert not any("registry" in name.lower() for name in public_names)


def test_settings_module_is_unmodified_by_capability_package_existence() -> None:
    """Importing the capability/usage modules must not alter CodestrataSettings defaults."""

    from codestrata.config.settings import AiSettings

    for module_name in _CAPABILITY_MODULES:
        importlib.import_module(module_name)

    settings = AiSettings()
    assert settings.provider == "bedrock"
    assert settings.openai.answer_model == "gpt-4o-mini"


def test_capability_modules_import_no_forbidden_runtime_or_sdk_dependencies() -> None:
    """None of the new modules may import os/boto3/openai/httpx or provider concretes."""

    engine_root = _engine_root()
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
    offenders: dict[str, set[str]] = {}
    for module_name in _CAPABILITY_MODULES:
        relative_path = "src/" + module_name.replace(".", "/") + ".py"
        path = engine_root / relative_path
        imported = _imported_module_names(path)
        hits = {
            name
            for name in imported
            for prefix in forbidden_prefixes
            if name == prefix or name.startswith(prefix + ".")
        }
        if hits:
            offenders[module_name] = hits
    assert offenders == {}, f"capability/usage modules import forbidden dependencies: {offenders}"
