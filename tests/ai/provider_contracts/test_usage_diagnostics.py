"""Tests for ``usage_availability_view``."""

from __future__ import annotations

from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_diagnostics import usage_availability_view


def test_availability_view_is_all_false_for_an_empty_record() -> None:
    view = usage_availability_view(ProviderUsageMetadata())
    assert all(value is False for value in view.values())


def test_availability_view_reports_true_only_for_populated_fields() -> None:
    usage = ProviderUsageMetadata(input_tokens=1, completion_status=UsageCompletionStatus.SUCCESS)
    view = usage_availability_view(usage)
    assert view["has_input_tokens"] is True
    assert view["has_completion_status"] is True
    assert view["has_output_tokens"] is False
    assert view["has_total_tokens"] is False
    assert view["has_latency_ms"] is False
    assert view["has_request_count"] is False
    assert view["has_retry_count"] is False


def test_availability_view_values_are_always_booleans() -> None:
    usage = ProviderUsageMetadata(
        input_tokens=0, output_tokens=0, total_tokens=0, latency_ms=0.0, retry_count=0
    )
    view = usage_availability_view(usage)
    assert all(isinstance(value, bool) for value in view.values())
    # Zero is a legitimate reported value, not "absent" — the view must
    # report availability (True), never confuse falsy-zero with missing.
    assert view["has_input_tokens"] is True
    assert view["has_latency_ms"] is True
    assert view["has_retry_count"] is True
