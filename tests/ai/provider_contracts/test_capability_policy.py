"""Tests for ``capability_policy`` constants."""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_policy import (
    ALLOWED_CAPABILITY_FEATURE_FLAGS,
    ALLOWED_CAPABILITY_LIMITATIONS,
    CAPABILITY_ALLOWED_CAPABILITY_IDS,
    CAPABILITY_ALLOWED_PROVIDER_IDS,
    CONTRACT_ID,
    CONTRACT_VERSION,
    HARD_CONSTRAINTS,
    POLICY_ID,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SLICE_ID,
)


def test_policy_and_contract_ids_are_versioned_and_stable() -> None:
    assert POLICY_ID == "community-ai-provider-capability-policy:1.0"
    assert CONTRACT_ID == "community-ai-provider-capability:1.0"
    assert CONTRACT_VERSION == "1.0"
    assert SLICE_ID == "11.5"


def test_allowed_provider_and_capability_ids_match_the_shared_policy() -> None:
    assert CAPABILITY_ALLOWED_PROVIDER_IDS == ("bedrock", "openai", "openrouter")
    assert CAPABILITY_ALLOWED_CAPABILITY_IDS == ("modernization_advisor",)


def test_allowed_feature_flags_cover_every_documented_flag() -> None:
    assert set(ALLOWED_CAPABILITY_FEATURE_FLAGS) == {
        "supports_structured_json",
        "supports_streaming",
        "supports_timeout_policy",
        "supports_retry_policy",
        "reports_usage_metadata",
        "reports_token_accounting",
    }


def test_allowed_limitations_is_bounded() -> None:
    assert set(ALLOWED_CAPABILITY_LIMITATIONS) == {
        "prompt_instruction_only",
        "not_wired_to_runtime",
        "streaming_not_implemented",
        "runtime_unregistered",
        "configuration_deferred",
        "authentication_deferred",
        "model_support_for_structured_json_varies",
    }


def test_openrouter_is_an_allowed_capability_provider_id() -> None:
    assert "openrouter" in CAPABILITY_ALLOWED_PROVIDER_IDS


def test_required_compatibility_requirement_ids_are_cr1_through_cr6() -> None:
    assert REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == (
        "CR-1",
        "CR-2",
        "CR-3",
        "CR-4",
        "CR-5",
        "CR-6",
    )


def test_hard_constraints_forbid_starting_slice_11_6_and_migrating_providers() -> None:
    assert "do_not_start_slice_11_6" in HARD_CONSTRAINTS
    assert "do_not_migrate_openai_or_bedrock" in HARD_CONSTRAINTS
    assert "do_not_commit_changes" in HARD_CONSTRAINTS
