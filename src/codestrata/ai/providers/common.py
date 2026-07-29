"""Shared helpers for production AI providers (Phase 5.8)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from codestrata.security.database_url import sanitize_exception_message

logger = logging.getLogger(__name__)


class ProviderThrottlingError(RuntimeError):
    """Raised when a provider rate-limits or throttles the request."""


class ProviderAuthenticationError(RuntimeError):
    """Raised when provider credentials are missing or rejected."""


class ProviderTimeoutError(RuntimeError):
    """Raised when a provider call exceeds the configured timeout."""


def categorize_provider_error(exc: BaseException) -> str:
    text = sanitize_exception_message(str(exc)).lower()
    name = type(exc).__name__.lower()
    if "throttl" in text or "rate" in text or "429" in text or "too many" in text:
        return "throttling"
    if (
        "auth" in text
        or "credential" in text
        or "api key" in text
        or "unauthorized" in text
        or "403" in text
        or "401" in text
        or "accessdenied" in name
    ):
        return "authentication"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "validation" in text or "schema" in text or "json" in text:
        return "validation"
    return "provider_error"


def retry_call[T](
    operation: Callable[[], T],
    *,
    max_retries: int,
    retry_on: tuple[type[BaseException], ...] = (ProviderThrottlingError,),
    sleep: Callable[[float], None] = time.sleep,
    base_delay_seconds: float = 0.5,
) -> T:
    """Retry ``operation`` with exponential backoff for selected exceptions."""

    attempts = max(1, int(max_retries))
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retry_on as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            logger.info(
                "provider_retry attempt=%s delay=%.2f category=%s",
                attempt,
                delay,
                categorize_provider_error(exc),
            )
            sleep(delay)
    assert last_error is not None
    raise last_error


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    blocked = {"authorization", "api-key", "x-api-key", "cookie"}
    return {
        key: ("***" if key.lower() in blocked else value)
        for key, value in headers.items()
    }
