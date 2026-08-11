"""Tests for ``usage_validation`` helpers, including the new ``completion_status`` field."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_validation import (
    validate_completion_status_is_known,
    validate_usage_metadata,
)


def test_completion_status_defaults_to_none() -> None:
    usage = ProviderUsageMetadata()
    assert usage.completion_status is None


@pytest.mark.parametrize(
    "status",
    [
        UsageCompletionStatus.SUCCESS,
        UsageCompletionStatus.UNAVAILABLE,
        UsageCompletionStatus.FAILED,
        UsageCompletionStatus.SKIPPED,
    ],
)
def test_every_completion_status_value_is_accepted(status: UsageCompletionStatus) -> None:
    usage = ProviderUsageMetadata(completion_status=status)
    assert usage.completion_status is status


def test_completion_status_rejects_a_non_enum_value() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderUsageMetadata(completion_status="success")  # type: ignore[arg-type]


def test_completion_status_does_not_affect_token_total_validation() -> None:
    usage = ProviderUsageMetadata(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        completion_status=UsageCompletionStatus.SUCCESS,
    )
    assert usage.total_tokens == 15
    with pytest.raises(ProviderContractValidationError):
        ProviderUsageMetadata(
            input_tokens=10,
            output_tokens=5,
            total_tokens=999,
            completion_status=UsageCompletionStatus.SUCCESS,
        )


def test_validate_usage_metadata_accepts_a_fully_populated_record() -> None:
    usage = ProviderUsageMetadata(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        latency_ms=42.0,
        request_count=1,
        retry_count=0,
        completion_status=UsageCompletionStatus.SUCCESS,
    )
    validate_usage_metadata(usage)


def test_validate_usage_metadata_accepts_an_empty_record() -> None:
    validate_usage_metadata(ProviderUsageMetadata())


def test_validate_usage_metadata_rejects_a_non_usage_object() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_usage_metadata(object())  # type: ignore[arg-type]


def test_validate_completion_status_is_known_accepts_every_allowed_value() -> None:
    for value in ("success", "unavailable", "failed", "skipped"):
        validate_completion_status_is_known(value)


def test_validate_completion_status_is_known_rejects_an_unknown_string() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_completion_status_is_known("errored")


def test_validate_completion_status_is_known_rejects_a_non_string() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_completion_status_is_known(1)  # type: ignore[arg-type]
