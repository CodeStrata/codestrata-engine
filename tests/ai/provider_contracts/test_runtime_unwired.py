"""Runtime-behavior test: the product path is unaffected by this package's existence.

Importing ``codestrata.ai.provider_contracts`` must not register anything,
must not construct a default registry, must not perform any I/O, and must
not change the behavior of the existing assess provider registry/factory.
"""

from __future__ import annotations

import importlib

from codestrata.extensions.assess_ai import (
    get_assess_ai_provider_registry,
    reset_assess_ai_provider_registry_for_tests,
)


def test_importing_provider_contracts_does_not_touch_assess_registry() -> None:
    reset_assess_ai_provider_registry_for_tests()
    before = get_assess_ai_provider_registry().list_providers()

    importlib.import_module("codestrata.ai.provider_contracts")
    importlib.import_module("codestrata.ai.provider_contracts.registry")
    importlib.import_module("codestrata.ai.provider_contracts.provider")

    reset_assess_ai_provider_registry_for_tests()
    after = get_assess_ai_provider_registry().list_providers()
    assert before == after == ("bedrock", "openai", "openrouter")
    reset_assess_ai_provider_registry_for_tests()


def test_provider_contracts_package_defines_no_process_wide_default_registry() -> None:
    registry_module = importlib.import_module("codestrata.ai.provider_contracts.registry")
    module_level_names = {name for name in dir(registry_module) if not name.startswith("_")}
    assert "get_default_registry" not in module_level_names
    assert "DEFAULT_REGISTRY" not in module_level_names


def test_provider_contracts_package_is_not_reexported_from_ai_providers() -> None:
    providers_module = importlib.import_module("codestrata.ai.providers")
    exported = set(getattr(providers_module, "__all__", []))
    assert not any("provider_contracts" in name.lower() for name in exported)
    assert not hasattr(providers_module, "AIProvider")
    assert not hasattr(providers_module, "provider_contracts")


def test_ai_enrichment_service_module_does_not_reference_provider_contracts() -> None:
    import codestrata.ai.enrichment.service as enrichment_service

    assert "provider_contracts" not in dir(enrichment_service)
