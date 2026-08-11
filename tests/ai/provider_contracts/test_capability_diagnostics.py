"""Tests for ``diagnostic_view_of_capability_profile``."""

from __future__ import annotations

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_diagnostics import (
    diagnostic_view_of_capability_profile,
)


def test_diagnostic_view_has_the_expected_bounded_keys() -> None:
    view = diagnostic_view_of_capability_profile(OPENAI_CAPABILITY_PROFILE)
    assert set(view) == {
        "limitations",
        "provider_id",
        "reports_token_accounting",
        "reports_usage_metadata",
        "schema_version",
        "supported_capability_ids",
        "supports_retry_policy",
        "supports_streaming",
        "supports_structured_json",
        "supports_timeout_policy",
    }


def test_diagnostic_view_uses_plain_strings_for_identifiers() -> None:
    view = diagnostic_view_of_capability_profile(BEDROCK_CAPABILITY_PROFILE)
    assert view["provider_id"] == "bedrock"
    assert view["supported_capability_ids"] == ["modernization_advisor"]


def test_diagnostic_view_limitations_are_sorted() -> None:
    view = diagnostic_view_of_capability_profile(BEDROCK_CAPABILITY_PROFILE)
    assert view["limitations"] == sorted(view["limitations"])


def test_diagnostic_view_reflects_the_intentional_structured_json_difference() -> None:
    openai_view = diagnostic_view_of_capability_profile(OPENAI_CAPABILITY_PROFILE)
    bedrock_view = diagnostic_view_of_capability_profile(BEDROCK_CAPABILITY_PROFILE)
    assert openai_view["supports_structured_json"] is True
    assert bedrock_view["supports_structured_json"] is False
