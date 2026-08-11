"""Tests for Slice 11.3 configuration_policy constants."""

from __future__ import annotations

from codestrata.ai.provider_contracts import configuration_policy as policy
from codestrata.ai.provider_contracts.policy import ALLOWED_PROVIDER_IDS


def test_policy_and_contract_identifiers() -> None:
    assert policy.POLICY_ID == "community-ai-provider-configuration-policy:1.0"
    assert policy.CONTRACT_ID == "community-ai-provider-configuration:1.0"
    assert policy.CONTRACT_VERSION == "1.0"
    assert policy.SLICE_ID == "11.3"


def test_configuration_provider_ids_match_slice_11_2_provider_ids() -> None:
    assert tuple(sorted(policy.CONFIGURATION_ALLOWED_PROVIDER_IDS)) == tuple(
        sorted(ALLOWED_PROVIDER_IDS)
    )


def test_default_provider_and_models_match_ground_truth() -> None:
    assert policy.DEFAULT_PROVIDER_ID == "bedrock"
    assert policy.DEFAULT_MODEL_BY_PROVIDER == {
        "bedrock": "amazon.nova-lite-v1:0",
        "openai": "gpt-4o-mini",
    }


def test_allowed_source_categories_are_the_expected_four_values() -> None:
    assert policy.ALLOWED_SOURCE_CATEGORIES == (
        "cli",
        "environment",
        "configuration_file",
        "default",
    )


def test_allowed_credential_kinds_and_availability_statuses() -> None:
    assert policy.ALLOWED_CREDENTIAL_KINDS == ("api_key", "aws_default_chain", "aws_profile")
    assert policy.ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES == ("present", "absent", "unknown")


def test_required_compatibility_requirement_ids_are_cr1_through_cr6() -> None:
    assert policy.REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == (
        "CR-1",
        "CR-2",
        "CR-3",
        "CR-4",
        "CR-5",
        "CR-6",
    )


def test_hard_constraints_document_slice_11_4_and_no_wiring() -> None:
    assert "do_not_start_slice_11_4" in policy.HARD_CONSTRAINTS
    assert "do_not_wire_configuration_to_ai_provider_protocol" in policy.HARD_CONSTRAINTS
    assert "do_not_commit_changes" in policy.HARD_CONSTRAINTS


def test_openrouter_is_allowed_but_not_a_default_model_provider() -> None:
    assert "openrouter" in policy.CONFIGURATION_ALLOWED_PROVIDER_IDS
    assert "openrouter" not in policy.DEFAULT_MODEL_BY_PROVIDER
    assert set(policy.DEFAULT_MODEL_BY_PROVIDER) == {"bedrock", "openai"}
