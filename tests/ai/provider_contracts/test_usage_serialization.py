"""Tests for ``usage_serialization``."""

from __future__ import annotations

import json

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_serialization import (
    canonical_json,
    diagnostic_view_of_usage,
    private_view_of_usage,
    serialize_usage_for_diagnostics,
    serialize_usage_private,
    usage_view,
)

_USAGE = ProviderUsageMetadata(
    input_tokens=10,
    output_tokens=5,
    total_tokens=15,
    latency_ms=42.5,
    request_count=1,
    retry_count=0,
    completion_status=UsageCompletionStatus.SUCCESS,
)


def test_usage_view_has_the_expected_bounded_keys() -> None:
    view = usage_view(_USAGE)
    assert set(view) == {
        "completion_status",
        "input_tokens",
        "latency_ms",
        "output_tokens",
        "request_count",
        "retry_count",
        "total_tokens",
    }


def test_usage_view_serializes_completion_status_as_a_plain_string() -> None:
    view = usage_view(_USAGE)
    assert view["completion_status"] == "success"


def test_usage_view_reports_none_for_an_absent_completion_status() -> None:
    view = usage_view(ProviderUsageMetadata())
    assert view["completion_status"] is None


def test_private_and_diagnostic_views_are_identical() -> None:
    assert private_view_of_usage(_USAGE) == diagnostic_view_of_usage(_USAGE)


def test_serialized_private_and_diagnostic_forms_are_identical() -> None:
    assert serialize_usage_private(_USAGE) == serialize_usage_for_diagnostics(_USAGE)


def test_serialize_usage_for_diagnostics_is_valid_and_deterministic_json() -> None:
    first = serialize_usage_for_diagnostics(_USAGE)
    second = serialize_usage_for_diagnostics(_USAGE)
    assert first == second
    payload = json.loads(first)
    assert payload["total_tokens"] == 15


def test_canonical_json_is_compact_and_sorted() -> None:
    text = serialize_usage_for_diagnostics(_USAGE)
    assert canonical_json(json.loads(text)) == text
