"""Unit tests for provider_contracts.validation helpers."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.validation import (
    validate_bounded_range,
    validate_non_empty_text,
    validate_non_negative,
    validate_usage_token_consistency,
)


def test_validate_non_empty_text_accepts_nonblank() -> None:
    validate_non_empty_text("hello", field_name="x")


@pytest.mark.parametrize("value", ["", "   "])
def test_validate_non_empty_text_rejects_blank(value: str) -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_non_empty_text(value, field_name="x")


def test_validate_non_negative_accepts_none_and_nonnegative() -> None:
    validate_non_negative(None, field_name="x")
    validate_non_negative(0, field_name="x")
    validate_non_negative(1.5, field_name="x")


def test_validate_non_negative_rejects_negative() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_non_negative(-1, field_name="x")


def test_validate_usage_token_consistency_allows_partial_data() -> None:
    validate_usage_token_consistency(input_tokens=1, output_tokens=None, total_tokens=None)


def test_validate_usage_token_consistency_enforces_sum_when_all_present() -> None:
    validate_usage_token_consistency(input_tokens=1, output_tokens=2, total_tokens=3)
    with pytest.raises(ProviderContractValidationError):
        validate_usage_token_consistency(input_tokens=1, output_tokens=2, total_tokens=4)


def test_validate_bounded_range_none_is_always_allowed() -> None:
    validate_bounded_range(None, field_name="x", minimum=0, maximum=1)


def test_validate_bounded_range_enforces_inclusive_bounds_by_default() -> None:
    validate_bounded_range(0, field_name="x", minimum=0, maximum=1)
    validate_bounded_range(1, field_name="x", minimum=0, maximum=1)
    with pytest.raises(ProviderContractValidationError):
        validate_bounded_range(1.1, field_name="x", minimum=0, maximum=1)


def test_validate_bounded_range_exclusive_minimum() -> None:
    with pytest.raises(ProviderContractValidationError):
        validate_bounded_range(0, field_name="x", minimum=0, maximum=1, inclusive_minimum=False)
    validate_bounded_range(0.01, field_name="x", minimum=0, maximum=1, inclusive_minimum=False)
