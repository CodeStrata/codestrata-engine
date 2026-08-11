"""Tests for LegacyConfigurationInput and its mapping translation."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.legacy_configuration import (
    LegacyConfigurationInput,
    legacy_configuration_input_from_mapping,
)


def test_legacy_configuration_input_defaults() -> None:
    input_data = LegacyConfigurationInput()
    assert input_data.provider is None
    assert input_data.openai_api_key_present is False
    assert input_data.ai_requested is None


def test_legacy_configuration_input_rejects_negative_timeout() -> None:
    with pytest.raises(ProviderContractValidationError):
        LegacyConfigurationInput(timeout_seconds=-1)


def test_legacy_configuration_input_rejects_negative_max_retries() -> None:
    with pytest.raises(ProviderContractValidationError):
        LegacyConfigurationInput(max_retries=-1)


def test_legacy_configuration_input_rejects_non_bool_flag() -> None:
    with pytest.raises(ProviderContractValidationError):
        LegacyConfigurationInput(openai_api_key_present="yes")  # type: ignore[arg-type]


def test_legacy_configuration_input_rejects_non_bool_ai_requested() -> None:
    with pytest.raises(ProviderContractValidationError):
        LegacyConfigurationInput(ai_requested="yes")  # type: ignore[arg-type]


def test_from_mapping_translates_known_keys() -> None:
    input_data = legacy_configuration_input_from_mapping(
        {
            "provider": "openai",
            "cli_model_id": "gpt-4o",
            "env_model_id": None,
            "file_model_id": "gpt-4o-mini",
            "openai_api_key_env_name": "OPENAI_API_KEY",
            "openai_api_key_present": True,
            "openai_base_url_configured": False,
            "bedrock_region_configured": False,
            "bedrock_profile_configured": False,
            "timeout_seconds": 30,
            "max_retries": 2,
            "ai_requested": True,
        }
    )
    assert input_data.provider == "openai"
    assert input_data.cli_model_id == "gpt-4o"
    assert input_data.env_model_id is None
    assert input_data.openai_api_key_present is True
    assert input_data.timeout_seconds == 30
    assert input_data.max_retries == 2
    assert input_data.ai_requested is True


def test_from_mapping_ignores_unknown_keys() -> None:
    input_data = legacy_configuration_input_from_mapping({"unexpected_key": "value"})
    assert input_data == LegacyConfigurationInput()


def test_from_mapping_defaults_booleans_when_absent() -> None:
    input_data = legacy_configuration_input_from_mapping({})
    assert input_data.openai_api_key_present is False
    assert input_data.bedrock_region_configured is False
    assert input_data.ai_requested is None


def test_from_mapping_rejects_non_mapping() -> None:
    with pytest.raises(ProviderContractValidationError):
        legacy_configuration_input_from_mapping(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_from_mapping_rejects_bool_for_int_field() -> None:
    with pytest.raises(ProviderContractValidationError):
        legacy_configuration_input_from_mapping({"timeout_seconds": True})


def test_from_mapping_performs_no_environment_or_filesystem_access() -> None:
    """Structural guarantee: this module never imports os or pathlib."""

    import ast
    import inspect

    import codestrata.ai.provider_contracts.legacy_configuration as module

    tree = ast.parse(inspect.getsource(module))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
    assert "os" not in imported_names
    assert "pathlib" not in imported_names
    assert "subprocess" not in imported_names
