"""Tests for ``usage_policy`` constants."""

from __future__ import annotations

from codestrata.ai.provider_contracts.policy import ALLOWED_EXECUTION_STATUSES
from codestrata.ai.provider_contracts.usage_policy import (
    ALLOWED_USAGE_COMPLETION_STATUSES,
    CONTRACT_ID,
    CONTRACT_VERSION,
    FORBIDDEN_USAGE_FIELD_NAMES,
    POLICY_ID,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
    SLICE_ID,
)


def test_policy_and_contract_ids_are_versioned_and_stable() -> None:
    assert POLICY_ID == "community-ai-provider-usage-policy:1.0"
    assert CONTRACT_ID == "community-ai-provider-usage:1.0"
    assert CONTRACT_VERSION == "1.0"
    assert SLICE_ID == "11.5"


def test_allowed_completion_statuses_matches_execution_statuses() -> None:
    assert ALLOWED_USAGE_COMPLETION_STATUSES == ALLOWED_EXECUTION_STATUSES
    assert ALLOWED_USAGE_COMPLETION_STATUSES == ("success", "unavailable", "failed", "skipped")


def test_forbidden_field_names_exclude_cost_pricing_billing_and_content() -> None:
    for token in ("cost", "price", "pricing", "billing", "prompt", "response", "exception"):
        assert any(token in name for name in FORBIDDEN_USAGE_FIELD_NAMES)


def test_required_compatibility_requirement_ids_are_cr1_through_cr6() -> None:
    assert REQUIRED_COMPATIBILITY_REQUIREMENT_IDS == (
        "CR-1",
        "CR-2",
        "CR-3",
        "CR-4",
        "CR-5",
        "CR-6",
    )
