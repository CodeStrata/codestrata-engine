"""Construct the OpenAI adapter and its executor without touching credentials.

Calling either builder here imports no SDK, reads no environment variable,
opens no file, and constructs no client — the credential boundary is only
crossed inside ``client.resolve_client``, which the adapter reaches on its
first ``execute()``.

:func:`build_openai_executor` pins the two Slice 11.4 policies:

* ``DEFAULT_RETRY_POLICY`` (``maximum_attempts=1``) — exactly one provider
  call per assess run, preserving CR-1. ``OpenAISettings.max_retries``
  (default ``3``) is still *not* wired to anything; it is only represented on
  ``OpenAIAdapterConfiguration`` for diagnostics.
* ``DEFAULT_TIMEOUT_POLICY`` (60s, ``provider_request`` scope) — a
  declarative statement of the bound. Real enforcement remains the OpenAI
  client's own ``timeout=`` argument, which ``client.py`` sets from the same
  60s default (``codestrata.ai.providers.models.DEFAULT_TIMEOUT_SECONDS``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codestrata.ai.provider_adapters.openai import client as client_module
from codestrata.ai.provider_adapters.openai.adapter import DetailSink, OpenAIProvider
from codestrata.ai.provider_adapters.openai.configuration import (
    OpenAIRuntimeConfiguration,
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
from codestrata.config.settings import CodestrataSettings, OpenAISettings

# The executor policies the OpenAI adapter runs under. Named constants so both
# the wrapper and the verification suite assert against the same objects.
OPENAI_RETRY_POLICY: AIProviderRetryPolicy = DEFAULT_RETRY_POLICY
OPENAI_TIMEOUT_POLICY: TimeoutPolicy = DEFAULT_TIMEOUT_POLICY
OPENAI_BACKOFF_POLICY: BackoffPolicy = DEFAULT_BACKOFF_POLICY


def resolve_openai_settings(
    *,
    settings: CodestrataSettings | None = None,
    openai_settings: OpenAISettings | None = None,
) -> OpenAISettings:
    """Resolve the OpenAI settings block, preserving the pre-migration precedence."""

    if openai_settings is not None:
        return openai_settings
    if settings is not None:
        return settings.ai.openai
    return OpenAISettings()


def build_openai_provider(
    *,
    settings: CodestrataSettings | None = None,
    openai_settings: OpenAISettings | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: Any | None = None,
    environment_reader: client_module.EnvironmentReader | None = None,
    detail_sink: DetailSink | None = None,
    configuration: OpenAIRuntimeConfiguration | None = None,
) -> OpenAIProvider:
    """Build an :class:`OpenAIProvider`. Constructs no client and reads no environment."""

    runtime_configuration = configuration or build_runtime_configuration(
        openai_settings=resolve_openai_settings(
            settings=settings, openai_settings=openai_settings
        ),
        timeout_seconds=timeout_seconds,
    )
    return OpenAIProvider(
        runtime_configuration,
        client=client,
        environment_reader=environment_reader,
        detail_sink=detail_sink,
    )


def build_openai_executor(
    provider: OpenAIProvider,
    *,
    sleeper: Callable[[float], None] | None = None,
    retry_policy: AIProviderRetryPolicy = OPENAI_RETRY_POLICY,
    timeout_policy: TimeoutPolicy = OPENAI_TIMEOUT_POLICY,
    backoff_policy: BackoffPolicy = OPENAI_BACKOFF_POLICY,
) -> AIProviderExecutor:
    """Wrap ``provider`` in an ``AIProviderExecutor`` under the pinned policies.

    ``sleeper`` defaults to a no-op rather than ``time.sleep``: with
    ``maximum_attempts=1`` no backoff delay is ever requested, and a no-op
    default guarantees that remains true even if a caller supplies a
    multi-attempt policy in a test.
    """

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
    "OPENAI_BACKOFF_POLICY",
    "OPENAI_RETRY_POLICY",
    "OPENAI_TIMEOUT_POLICY",
    "build_openai_executor",
    "build_openai_provider",
    "resolve_openai_settings",
]
