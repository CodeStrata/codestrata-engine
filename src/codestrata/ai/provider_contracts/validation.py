"""Shared, reusable validation helpers.

Every dataclass in this package validates itself in ``__post_init__``; the
functions here are the same logic exposed standalone so tests (and any
future capability/adapter code) can validate values before constructing a
contract object, without duplicating the rules.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError


def validate_non_empty_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProviderContractValidationError(f"{field_name} must be a non-empty string")


def validate_non_negative(value: int | float | None, *, field_name: str) -> None:
    if value is not None and value < 0:
        raise ProviderContractValidationError(f"{field_name} must be non-negative")


def validate_usage_token_consistency(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
) -> None:
    if (
        input_tokens is not None
        and output_tokens is not None
        and total_tokens is not None
        and total_tokens != input_tokens + output_tokens
    ):
        raise ProviderContractValidationError(
            "total_tokens must equal input_tokens + output_tokens when all three are present"
        )


def validate_bounded_range(
    value: float | None,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
    inclusive_minimum: bool = True,
) -> None:
    if value is None:
        return
    lower_ok = value >= minimum if inclusive_minimum else value > minimum
    if not (lower_ok and value <= maximum):
        boundary = "[" if inclusive_minimum else "("
        raise ProviderContractValidationError(
            f"{field_name} must be within {boundary}{minimum}, {maximum}]"
        )


__all__ = [
    "validate_bounded_range",
    "validate_non_empty_text",
    "validate_non_negative",
    "validate_usage_token_consistency",
]
