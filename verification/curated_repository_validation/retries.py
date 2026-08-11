"""Bounded retry helpers for SV.10."""

from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


def should_retry_clone(detail: str) -> bool:
    lowered = detail.lower()
    transient = (
        "timed out",
        "timeout",
        "connection reset",
        "temporary failure",
        "could not resolve host",
        "network is unreachable",
        "tls handshake",
        "http 502",
        "http 503",
        "http 429",
    )
    return any(token in lowered for token in transient)


def retry_once(
    operation: Callable[[], T],
    *,
    should_retry: Callable[[T], bool],
) -> tuple[T, list[dict[str, str]]]:
    """Run *operation* once, optionally retry once when *should_retry* returns True."""

    retries: list[dict[str, str]] = []
    first = operation()
    if not should_retry(first):
        return first, retries
    retries.append({"attempt": "1", "reason": "transient_failure"})
    second = operation()
    retries.append({"attempt": "2", "reason": "retry_completed"})
    return second, retries
