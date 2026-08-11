"""AI analytics catalog tests (Slice 10.6)."""

from __future__ import annotations

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    APPROVED_AI_CAPABILITIES,
    APPROVED_AI_FAILURE_CATEGORIES,
    APPROVED_AI_MODEL_FAMILIES,
    APPROVED_AI_OUTCOMES,
    APPROVED_AI_PROVIDER_FAMILIES,
    APPROVED_AI_PROVIDER_OWNERSHIPS,
)


def test_capability_catalog_closed() -> None:
    assert APPROVED_AI_CAPABILITIES == frozenset({"modernization_advisor"})


def test_provider_family_catalog() -> None:
    assert "openai" in APPROVED_AI_PROVIDER_FAMILIES
    assert "aws_bedrock" in APPROVED_AI_PROVIDER_FAMILIES
    assert "openrouter" in APPROVED_AI_PROVIDER_FAMILIES


def test_model_family_catalog() -> None:
    assert APPROVED_AI_MODEL_FAMILIES == frozenset(
        {"amazon_nova_family", "gpt_family", "unavailable"}
    )


def test_ownership_and_outcome_vocabularies() -> None:
    assert "customer_managed" in APPROVED_AI_PROVIDER_OWNERSHIPS
    assert APPROVED_AI_OUTCOMES == frozenset(
        {"success", "failure", "unavailable", "skipped"}
    )
    assert "authentication_failed" in APPROVED_AI_FAILURE_CATEGORIES
