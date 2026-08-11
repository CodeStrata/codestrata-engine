"""Resolve assess-path timeout and retry policies from CodestrataSettings.

Community assess wires ``[ai.<provider>].timeout_seconds`` and
``max_retries`` so user-facing settings are not dead configuration.

Bounds:
- timeout: (0, MAX_TIMEOUT_SECONDS]
- retries: ``max_retries`` counts *retries only*; converted to
  ``maximum_attempts = max_retries + 1`` and capped by ``MAX_MAXIMUM_ATTEMPTS``.

Default settings (``timeout_seconds=60``, ``max_retries=3``) therefore mean
up to 4 finite attempts for transient/retryable provider errors. Auth and
validation failures remain non-retryable via ``AIProviderRetryPolicy``.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.execution_policy import MAX_MAXIMUM_ATTEMPTS
from codestrata.ai.provider_contracts.retry_policy import (
    AIProviderRetryPolicy,
    max_retries_to_maximum_attempts,
)
from codestrata.ai.provider_contracts.timeout_policy import (
    MAX_TIMEOUT_SECONDS,
    TimeoutPolicy,
)
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import CodestrataSettings


def provider_timeout_seconds(
    settings: CodestrataSettings | None,
    *,
    provider: str,
    explicit: float | None = None,
    provider_settings_timeout: int | float | None = None,
) -> float:
    """Resolve timeout seconds: explicit → provider settings block → default."""

    if explicit is not None:
        value = float(explicit)
    elif provider_settings_timeout is not None:
        value = float(provider_settings_timeout)
    elif settings is None:
        value = float(DEFAULT_TIMEOUT_SECONDS)
    else:
        key = provider.strip().lower()
        if key == "openai":
            value = float(settings.ai.openai.timeout_seconds)
        elif key == "openrouter":
            value = float(settings.ai.openrouter.timeout_seconds)
        else:
            value = float(settings.ai.bedrock.timeout_seconds)
    if not (0 < value <= MAX_TIMEOUT_SECONDS):
        raise ValueError(
            f"timeout_seconds must be within (0, {MAX_TIMEOUT_SECONDS}], got {value}"
        )
    return value


def provider_max_retries(
    settings: CodestrataSettings | None,
    *,
    provider: str,
) -> int:
    """Resolve settings-shaped max_retries (retries only, excluding first attempt)."""

    if settings is None:
        return 0
    key = provider.strip().lower()
    if key == "openai":
        return int(settings.ai.openai.max_retries)
    if key == "openrouter":
        return int(settings.ai.openrouter.max_retries)
    return int(settings.ai.bedrock.max_retries)


def assess_retry_policy(
    settings: CodestrataSettings | None,
    *,
    provider: str,
) -> AIProviderRetryPolicy:
    """Bounded retry policy derived from settings (finite; never unbounded)."""

    retries = provider_max_retries(settings, provider=provider)
    # Clamp retries so maximum_attempts stays within policy bounds.
    max_retries_allowed = MAX_MAXIMUM_ATTEMPTS - 1
    clamped = max(0, min(int(retries), max_retries_allowed))
    return AIProviderRetryPolicy(
        maximum_attempts=max_retries_to_maximum_attempts(clamped),
    )


def assess_timeout_policy(
    settings: CodestrataSettings | None,
    *,
    provider: str,
    explicit: float | None = None,
) -> TimeoutPolicy:
    return TimeoutPolicy(
        timeout_seconds=provider_timeout_seconds(
            settings, provider=provider, explicit=explicit
        )
    )


__all__ = [
    "assess_retry_policy",
    "assess_timeout_policy",
    "provider_max_retries",
    "provider_timeout_seconds",
]
