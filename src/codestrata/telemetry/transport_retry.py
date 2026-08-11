"""Bounded synchronous retry classification (Slice 9.11).

Default maximum attempts is 1 (no retry). When attempts=2, only transient
failures may retry with the exact same event_id and body.
"""

from __future__ import annotations

from codestrata.telemetry.transport_errors import TransportFailureCategory

# Status codes that may be retried when maximum_attempts > 1.
RETRYABLE_HTTP_STATUS: frozenset[int] = frozenset({502, 503, 504})

# Never retry these client / identity / auth outcomes.
NON_RETRYABLE_CATEGORIES: frozenset[TransportFailureCategory] = frozenset(
    {
        TransportFailureCategory.ACCEPTED,
        TransportFailureCategory.ALREADY_ACCEPTED,
        TransportFailureCategory.DISABLED,
        TransportFailureCategory.INVALID_CONFIGURATION,
        TransportFailureCategory.AUTHENTICATION_FAILED,
        TransportFailureCategory.AUTHORIZATION_DENIED,
        TransportFailureCategory.VALIDATION_REJECTED,
        TransportFailureCategory.CONFLICT,
        TransportFailureCategory.PAYLOAD_TOO_LARGE,
        TransportFailureCategory.REDIRECT_REJECTED,
        TransportFailureCategory.INVALID_RESPONSE,
        TransportFailureCategory.PRIVACY_REJECTED,
        TransportFailureCategory.RATE_LIMITED,
    }
)


def is_retryable_http_status(status_code: int) -> bool:
    return status_code in RETRYABLE_HTTP_STATUS


def is_retryable_category(category: TransportFailureCategory) -> bool:
    if category in NON_RETRYABLE_CATEGORIES:
        return False
    return category in {
        TransportFailureCategory.TIMEOUT,
        TransportFailureCategory.CONNECTION_FAILED,
        TransportFailureCategory.SERVER_UNAVAILABLE,
    }


def should_retry(
    *,
    attempt: int,
    maximum_attempts: int,
    category: TransportFailureCategory,
) -> bool:
    """Return True only for bounded transient retries within one send()."""

    if maximum_attempts <= 1:
        return False
    if attempt >= maximum_attempts:
        return False
    return is_retryable_category(category)


__all__ = [
    "NON_RETRYABLE_CATEGORIES",
    "RETRYABLE_HTTP_STATUS",
    "is_retryable_category",
    "is_retryable_http_status",
    "should_retry",
]
