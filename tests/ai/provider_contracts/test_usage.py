"""Unit tests for provider_contracts.usage."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata


def test_all_fields_optional() -> None:
    usage = ProviderUsageMetadata()
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None
    assert usage.latency_ms is None
    assert usage.request_count is None
    assert usage.retry_count is None


def test_consistent_totals_are_accepted() -> None:
    usage = ProviderUsageMetadata(input_tokens=10, output_tokens=5, total_tokens=15)
    assert usage.total_tokens == 15


def test_partial_usage_without_total_is_not_cross_validated() -> None:
    usage = ProviderUsageMetadata(input_tokens=10, output_tokens=5)
    assert usage.total_tokens is None


def test_inconsistent_totals_are_rejected() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderUsageMetadata(input_tokens=10, output_tokens=5, total_tokens=999)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"total_tokens": -1},
        {"request_count": -1},
        {"retry_count": -1},
        {"latency_ms": -0.5},
    ],
)
def test_negative_values_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderUsageMetadata(**kwargs)


def test_zero_values_are_accepted() -> None:
    usage = ProviderUsageMetadata(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        latency_ms=0.0,
        request_count=0,
        retry_count=0,
    )
    assert usage.total_tokens == 0
