"""Construct the OpenRouter adapter and executor without import-time credentials."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codestrata.ai.provider_adapters.openrouter import client as client_module
from codestrata.ai.provider_adapters.openrouter.adapter import DetailSink, OpenRouterProvider
from codestrata.ai.provider_adapters.openrouter.configuration import (
    OpenRouterRuntimeConfiguration,
    build_runtime_configuration,
)
from codestrata.ai.provider_contracts.backoff import DEFAULT_BACKOFF_POLICY, BackoffPolicy
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    AIProviderRetryPolicy,
)
from codestrata.ai.provider_contracts.timeout_policy import DEFAULT_TIMEOUT_POLICY, TimeoutPolicy
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import CodestrataSettings, OpenRouterSettings

OPENROUTER_RETRY_POLICY: AIProviderRetryPolicy = DEFAULT_RETRY_POLICY
OPENROUTER_TIMEOUT_POLICY: TimeoutPolicy = DEFAULT_TIMEOUT_POLICY
OPENROUTER_BACKOFF_POLICY: BackoffPolicy = DEFAULT_BACKOFF_POLICY


def resolve_openrouter_settings(
    *,
    settings: CodestrataSettings | None = None,
    openrouter_settings: OpenRouterSettings | None = None,
) -> OpenRouterSettings:
    if openrouter_settings is not None:
        return openrouter_settings
    if settings is not None:
        return settings.ai.openrouter
    return OpenRouterSettings()


def build_openrouter_provider(
    *,
    settings: CodestrataSettings | None = None,
    openrouter_settings: OpenRouterSettings | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: Any | None = None,
    environment_reader: client_module.EnvironmentReader | None = None,
    detail_sink: DetailSink | None = None,
    configuration: OpenRouterRuntimeConfiguration | None = None,
    api_key_present: bool = False,
) -> OpenRouterProvider:
    """Build an :class:`OpenRouterProvider`. Constructs no client and reads no environment."""

    resolved_settings = resolve_openrouter_settings(
        settings=settings, openrouter_settings=openrouter_settings
    )
    runtime_configuration = configuration or build_runtime_configuration(
        openrouter_settings=resolved_settings,
        timeout_seconds=timeout_seconds,
        api_key_present=api_key_present,
    )
    return OpenRouterProvider(
        runtime_configuration,
        client=client,
        environment_reader=environment_reader,
        detail_sink=detail_sink,
    )


def build_openrouter_executor(
    provider: OpenRouterProvider,
    *,
    sleeper: Callable[[float], None] | None = None,
    retry_policy: AIProviderRetryPolicy = OPENROUTER_RETRY_POLICY,
    timeout_policy: TimeoutPolicy = OPENROUTER_TIMEOUT_POLICY,
    backoff_policy: BackoffPolicy = OPENROUTER_BACKOFF_POLICY,
) -> AIProviderExecutor:
    """Wrap ``provider`` under pinned Slice 11.4 defaults (maximum_attempts=1)."""

    return AIProviderExecutor(
        provider,
        sleeper=sleeper if sleeper is not None else _no_sleep,
        retry_policy=retry_policy,
        timeout_policy=timeout_policy,
        backoff_policy=backoff_policy,
    )


def _no_sleep(_seconds: float) -> None:
    return None


__all__ = [
    "OPENROUTER_BACKOFF_POLICY",
    "OPENROUTER_RETRY_POLICY",
    "OPENROUTER_TIMEOUT_POLICY",
    "build_openrouter_executor",
    "build_openrouter_provider",
    "resolve_openrouter_settings",
]
