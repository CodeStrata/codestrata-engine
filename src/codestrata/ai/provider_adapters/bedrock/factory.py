"""Construct the Bedrock adapter and its executor without touching AWS.

Calling either builder here imports no SDK, reads no environment variable,
opens no file, resolves no AWS profile, and constructs no client — the AWS
boundary is only crossed inside ``client.resolve_client``, which the adapter
reaches on its first ``execute()``.

:func:`build_bedrock_executor` pins the two Slice 11.4 policies:

* ``DEFAULT_RETRY_POLICY`` (``maximum_attempts=1``) — exactly one provider
  call per assess run, preserving CR-1. ``BedrockSettings.max_retries``
  (default ``3``) is still *not* wired to anything; it is only represented on
  ``BedrockAdapterConfiguration`` for diagnostics. Stacking CodeStrata
  retries on top of the SDK's own retry handler is explicitly out of scope:
  ``aws_config.create_bedrock_runtime_client`` pins botocore to
  ``retries={"max_attempts": 1, "mode": "standard"}`` and that stays.
* ``DEFAULT_TIMEOUT_POLICY`` (60s, ``provider_request`` scope) — a
  declarative statement of the bound. Real enforcement remains the botocore
  ``Config(connect_timeout=..., read_timeout=...)`` that ``aws_config``
  derives from the same 60s default
  (``codestrata.ai.providers.models.DEFAULT_TIMEOUT_SECONDS``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from codestrata.ai.provider_adapters.bedrock.adapter import BedrockProvider, DetailSink
from codestrata.ai.provider_adapters.bedrock.configuration import (
    BedrockRuntimeConfiguration,
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
from codestrata.config.settings import CodestrataSettings

# The executor policies the Bedrock adapter runs under. Named constants so
# both the wrapper and the verification suite assert against the same objects.
BEDROCK_RETRY_POLICY: AIProviderRetryPolicy = DEFAULT_RETRY_POLICY
BEDROCK_TIMEOUT_POLICY: TimeoutPolicy = DEFAULT_TIMEOUT_POLICY
BEDROCK_BACKOFF_POLICY: BackoffPolicy = DEFAULT_BACKOFF_POLICY


def build_bedrock_provider(
    *,
    settings: CodestrataSettings | None = None,
    profile_name: str | None = None,
    region_name: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: Any | None = None,
    detail_sink: DetailSink | None = None,
    configuration: BedrockRuntimeConfiguration | None = None,
) -> BedrockProvider:
    """Build a :class:`BedrockProvider`. Constructs no client and reaches no AWS service."""

    runtime_configuration = configuration or build_runtime_configuration(
        settings=settings,
        profile_name=profile_name,
        region_name=region_name,
        timeout_seconds=timeout_seconds,
    )
    return BedrockProvider(
        runtime_configuration,
        client=client,
        detail_sink=detail_sink,
    )


def build_bedrock_executor(
    provider: BedrockProvider,
    *,
    sleeper: Callable[[float], None] | None = None,
    retry_policy: AIProviderRetryPolicy = BEDROCK_RETRY_POLICY,
    timeout_policy: TimeoutPolicy = BEDROCK_TIMEOUT_POLICY,
    backoff_policy: BackoffPolicy = BEDROCK_BACKOFF_POLICY,
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
    "BEDROCK_BACKOFF_POLICY",
    "BEDROCK_RETRY_POLICY",
    "BEDROCK_TIMEOUT_POLICY",
    "build_bedrock_executor",
    "build_bedrock_provider",
]
