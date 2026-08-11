"""Tests for the static baseline capability catalogs (bedrock, openai, openrouter)."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    KNOWN_PROVIDER_CAPABILITY_PROFILES,
    OPENAI_CAPABILITY_PROFILE,
    OPENROUTER_CAPABILITY_PROFILE,
    all_known_capability_profiles,
    capability_profile_for,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId


def test_bedrock_openai_and_openrouter_are_cataloged() -> None:
    assert set(KNOWN_PROVIDER_CAPABILITY_PROFILES) == {
        ProviderId.BEDROCK,
        ProviderId.OPENAI,
        ProviderId.OPENROUTER,
    }


def test_all_cataloged_profiles_declare_modernization_advisor() -> None:
    assert BEDROCK_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)
    assert OPENAI_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)
    assert OPENROUTER_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)


def test_openai_and_openrouter_support_structured_json_and_bedrock_does_not() -> None:
    assert OPENAI_CAPABILITY_PROFILE.supports_structured_json is True
    assert OPENROUTER_CAPABILITY_PROFILE.supports_structured_json is True
    assert BEDROCK_CAPABILITY_PROFILE.supports_structured_json is False
    assert "prompt_instruction_only" in BEDROCK_CAPABILITY_PROFILE.limitations


def test_no_cataloged_provider_declares_streaming_support() -> None:
    assert BEDROCK_CAPABILITY_PROFILE.supports_streaming is False
    assert OPENAI_CAPABILITY_PROFILE.supports_streaming is False
    assert OPENROUTER_CAPABILITY_PROFILE.supports_streaming is False


def test_migrated_providers_declare_timeout_and_retry_policy_readiness_as_not_wired() -> None:
    for profile in (BEDROCK_CAPABILITY_PROFILE, OPENAI_CAPABILITY_PROFILE):
        assert profile.supports_timeout_policy is True
        assert profile.supports_retry_policy is True
        assert "not_wired_to_runtime" in profile.limitations


def test_openrouter_profile_records_structured_json_model_variance() -> None:
    assert OPENROUTER_CAPABILITY_PROFILE.supports_timeout_policy is True
    assert OPENROUTER_CAPABILITY_PROFILE.supports_retry_policy is True
    assert "model_support_for_structured_json_varies" in OPENROUTER_CAPABILITY_PROFILE.limitations
    assert "runtime_unregistered" not in OPENROUTER_CAPABILITY_PROFILE.limitations


def test_all_cataloged_providers_report_usage_metadata_and_token_accounting() -> None:
    for profile in (
        BEDROCK_CAPABILITY_PROFILE,
        OPENAI_CAPABILITY_PROFILE,
        OPENROUTER_CAPABILITY_PROFILE,
    ):
        assert profile.reports_usage_metadata is True
        assert profile.reports_token_accounting is True


def test_capability_profile_for_returns_the_matching_static_profile() -> None:
    assert capability_profile_for(ProviderId.BEDROCK) is BEDROCK_CAPABILITY_PROFILE
    assert capability_profile_for(ProviderId.OPENAI) is OPENAI_CAPABILITY_PROFILE
    assert capability_profile_for(ProviderId.OPENROUTER) is OPENROUTER_CAPABILITY_PROFILE


def test_capability_profile_for_raises_key_error_for_unregistered_provider() -> None:
    with pytest.raises(KeyError):
        capability_profile_for("not-a-provider")  # type: ignore[arg-type]


def test_all_known_capability_profiles_is_sorted_and_stable() -> None:
    first = all_known_capability_profiles()
    second = all_known_capability_profiles()
    assert first == second
    assert [p.provider_id.value for p in first] == sorted(p.provider_id.value for p in first)


def test_catalog_profiles_are_module_level_singletons() -> None:
    import importlib

    module = importlib.import_module("codestrata.ai.provider_contracts.capability_catalogs")
    assert module.BEDROCK_CAPABILITY_PROFILE is BEDROCK_CAPABILITY_PROFILE
    assert module.OPENAI_CAPABILITY_PROFILE is OPENAI_CAPABILITY_PROFILE
    assert module.OPENROUTER_CAPABILITY_PROFILE is OPENROUTER_CAPABILITY_PROFILE
