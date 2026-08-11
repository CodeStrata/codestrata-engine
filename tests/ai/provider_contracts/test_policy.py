"""Unit tests for provider_contracts.policy constants."""

from __future__ import annotations

from codestrata.ai.provider_contracts import policy


def test_policy_and_contract_identifiers() -> None:
    assert policy.POLICY_ID == "community-ai-provider-contract-policy:1.0"
    assert policy.CONTRACT_ID == "community-ai-provider-contract:1.0"
    assert policy.CONTRACT_VERSION == "1.0"


def test_allowed_provider_ids_are_engine_ids_only() -> None:
    assert policy.ALLOWED_PROVIDER_IDS == ("bedrock", "openai", "openrouter")
    assert "aws_bedrock" not in policy.ALLOWED_PROVIDER_IDS
    assert "openrouter" in policy.ALLOWED_PROVIDER_IDS


def test_allowed_capability_ids_is_modernization_advisor_only() -> None:
    assert policy.ALLOWED_CAPABILITY_IDS == ("modernization_advisor",)


def test_allowed_response_expectations() -> None:
    assert policy.ALLOWED_RESPONSE_EXPECTATIONS == ("text", "structured_json")


def test_allowed_execution_statuses() -> None:
    assert policy.ALLOWED_EXECUTION_STATUSES == ("success", "unavailable", "failed", "skipped")


def test_allowed_error_categories_bounded_set() -> None:
    assert policy.ALLOWED_ERROR_CATEGORIES == (
        "missing_configuration",
        "dependency_unavailable",
        "authentication_failed",
        "authorization_failed",
        "invalid_model",
        "timeout",
        "rate_limited",
        "provider_unavailable",
        "invalid_request",
        "invalid_response",
        "parsing_failed",
        "internal_failure",
    )


def test_required_compatibility_requirement_ids_are_cr1_through_cr6() -> None:
    assert policy.REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == (
        "CR-1",
        "CR-2",
        "CR-3",
        "CR-4",
        "CR-5",
        "CR-6",
    )
