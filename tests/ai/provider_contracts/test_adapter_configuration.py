"""Tests for OpenAIAdapterConfiguration / BedrockAdapterConfiguration."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.adapter_configuration import (
    BedrockAdapterConfiguration,
    OpenAIAdapterConfiguration,
    build_bedrock_adapter_configuration,
    build_openai_adapter_configuration,
    validate_adapter_matches_provider,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId


def test_openai_adapter_configuration_defaults() -> None:
    adapter = OpenAIAdapterConfiguration()
    assert adapter.api_key_env_name is None
    assert adapter.api_key_present is False
    assert adapter.base_url is None
    assert adapter.base_url_configured is False
    assert adapter.max_retries is None


def test_openai_adapter_configuration_rejects_non_blank_url_without_configured_flag() -> None:
    with pytest.raises(ProviderContractValidationError):
        OpenAIAdapterConfiguration(base_url="https://example.test", base_url_configured=False)


def test_openai_adapter_configuration_allows_configured_without_stored_value() -> None:
    """Privacy-preferred path: base_url_configured=True with no stored raw value."""

    adapter = OpenAIAdapterConfiguration(base_url=None, base_url_configured=True)
    assert adapter.base_url is None
    assert adapter.base_url_configured is True


def test_openai_adapter_configuration_rejects_negative_max_retries() -> None:
    with pytest.raises(ProviderContractValidationError):
        OpenAIAdapterConfiguration(max_retries=-1)


def test_openai_adapter_configuration_redacted_never_includes_base_url() -> None:
    adapter = build_openai_adapter_configuration(
        api_key_env_name="OPENAI_API_KEY",
        api_key_present=True,
        base_url="https://proxy.internal.example/v1",
        max_retries=3,
    )
    view = adapter.redacted()
    assert "base_url" not in view
    assert view["base_url_configured"] is True
    assert "https://proxy.internal.example/v1" not in repr(view)
    assert view["api_key_env_name"] == "OPENAI_API_KEY"
    assert view["api_key_present"] is True
    assert view["max_retries_declared"] is True


def test_build_openai_adapter_configuration_derives_configured_flag_from_url() -> None:
    adapter = build_openai_adapter_configuration(
        api_key_env_name=None, api_key_present=False, base_url="   "
    )
    assert adapter.base_url is None
    assert adapter.base_url_configured is False


def test_build_openai_adapter_configuration_honors_explicit_configured_override() -> None:
    adapter = build_openai_adapter_configuration(
        api_key_env_name=None,
        api_key_present=False,
        base_url_configured=True,
    )
    assert adapter.base_url is None
    assert adapter.base_url_configured is True


def test_bedrock_adapter_configuration_defaults() -> None:
    adapter = BedrockAdapterConfiguration()
    assert adapter.region_configured is False
    assert adapter.profile_configured is False
    assert adapter.max_retries is None


def test_bedrock_adapter_configuration_has_no_endpoint_or_organization_fields() -> None:
    fields = {f.name for f in BedrockAdapterConfiguration.__dataclass_fields__.values()}
    assert "endpoint_url" not in fields
    assert "organization" not in fields
    assert "project" not in fields


def test_bedrock_adapter_configuration_redacted_never_includes_region_or_profile_values() -> None:
    adapter = build_bedrock_adapter_configuration(
        region_configured=True, profile_configured=True, max_retries=5
    )
    view = adapter.redacted()
    assert view == {
        "adapter_kind": "bedrock",
        "max_retries_declared": True,
        "profile_configured": True,
        "region_configured": True,
    }


def test_validate_adapter_matches_provider_accepts_correct_pairing() -> None:
    validate_adapter_matches_provider(ProviderId.OPENAI, OpenAIAdapterConfiguration())
    validate_adapter_matches_provider(ProviderId.BEDROCK, BedrockAdapterConfiguration())


def test_validate_adapter_matches_provider_rejects_mismatch() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_adapter_matches_provider(ProviderId.OPENAI, BedrockAdapterConfiguration())
    with pytest.raises(ProviderContractValidationError):
        validate_adapter_matches_provider(ProviderId.BEDROCK, OpenAIAdapterConfiguration())
