"""The single AWS boundary: lazy Bedrock Runtime client construction.

This is the **only** module in the adapter that reaches AWS at all. It does
so lazily — inside :func:`resolve_client`, never at import time — and only
through ``codestrata.ai.aws_config``, which owns the credential/profile/
region precedence chain and the ``botocore.config.Config`` timeouts. This
module never calls ``boto3.Session`` itself, never reads ``os.environ``, and
never reimplements any part of the credential chain. Consequences:

* Importing the adapter package, asking it for its ``provider_id``, or asking
  ``supports()`` never touches credentials, the SDK, the instance metadata
  service, STS, or the network.
* When AI enrichment is disabled, nothing here runs at all.
* Tests inject a client via ``injected_client=`` and never reach ``boto3``,
  ``aws_config``, or AWS.

**Lazy is a deliberate Slice 11.7 change.** The pre-migration provider built
its client eagerly in ``BedrockAIModelProvider.__init__``, so a missing
``boto3`` extra or an unusable AWS profile failed at *construction* time. It
now fails on the first ``execute()`` instead, as a bounded ``UNAVAILABLE``
result. The enrichment fail-soft path is unchanged because
``legacy_bridge.legacy_error_for`` still rebuilds the same
``AIProviderConfigurationError`` with the same message.

There is no process-wide client singleton. Each :func:`resolve_client` call
either returns the injected client or builds a fresh one, so no credential
state outlives a single invocation.

:func:`resolve_client` never raises for an expected configuration failure
(extra not installed, AWS authentication failed, client constructor failed)
— it returns a :class:`ClientResolution` carrying a bounded
``AIProviderError`` instead, preserving the adapter's "``execute()`` never
raises for expected failures" contract (CR-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import codestrata.ai.aws_config as aws_config
from codestrata.ai.provider_adapters.bedrock import error_mapping
from codestrata.ai.provider_adapters.bedrock.configuration import BedrockClientInputs
from codestrata.ai.provider_contracts.errors import AIProviderError

# Re-exported so the adapter, the wrapper, and tests can all name the same
# AWS boundary types without importing ``aws_config`` themselves.
AwsAuthenticationError = aws_config.AwsAuthenticationError
BedrockRuntimeClient = aws_config.BedrockRuntimeClient

CONVERSE_METHOD_NAME = "converse"


@dataclass(frozen=True, slots=True)
class BedrockClientHandle:
    """A constructed client plus the non-secret facts diagnostics may report.

    ``__repr__`` never renders the client object (whose own repr can echo an
    endpoint or a region), the profile name, or the region.
    """

    client: Any
    profile_configured: bool
    region_configured: bool
    injected: bool

    def __repr__(self) -> str:
        return (
            "BedrockClientHandle("
            f"profile_configured={self.profile_configured}, "
            f"region_configured={self.region_configured}, "
            f"injected={self.injected}, "
            "client_present=True)"
        )


@dataclass(frozen=True, slots=True)
class ClientResolution:
    """Either a usable client handle or a bounded reason why there is none."""

    handle: BedrockClientHandle | None = None
    error: AIProviderError | None = None
    legacy_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.handle is not None


def _failure(mapped: error_mapping.MappedFailure) -> ClientResolution:
    return ClientResolution(error=mapped.error, legacy_detail=mapped.legacy_detail)


def resolve_client(
    inputs: BedrockClientInputs,
    *,
    injected_client: Any | None = None,
) -> ClientResolution:
    """Return a client handle for ``inputs``, or a bounded error explaining why not.

    The explicit ``profile_name``/``region_name`` on ``inputs`` are passed
    through to ``aws_config.create_bedrock_runtime_client`` unmodified, so
    the documented precedence (explicit argument, then environment, then
    settings) is resolved in exactly one place.
    """

    profile_configured = inputs.profile_configured
    region_configured = inputs.region_configured

    if injected_client is not None:
        return ClientResolution(
            handle=BedrockClientHandle(
                client=injected_client,
                profile_configured=profile_configured,
                region_configured=region_configured,
                injected=True,
            )
        )

    try:
        client = aws_config.create_bedrock_runtime_client(
            settings=inputs.settings,
            profile=inputs.profile_name,
            region=inputs.region_name,
            timeout_seconds=inputs.timeout_seconds,
        )
    except aws_config.AwsAuthenticationError as error:
        # Must precede RuntimeError: AwsAuthenticationError subclasses it.
        return _failure(error_mapping.classify_client_authentication_failure(error))
    except RuntimeError as error:
        # aws_config raises a bare RuntimeError only when boto3 is missing.
        return _failure(error_mapping.classify_missing_dependency(error))
    except Exception as error:  # noqa: BLE001 - provider construction boundary
        return _failure(error_mapping.classify_client_construction_failure(error))

    return ClientResolution(
        handle=BedrockClientHandle(
            client=client,
            profile_configured=profile_configured,
            region_configured=region_configured,
            injected=False,
        )
    )


def bedrock_extra_importable() -> bool:
    """Return whether the optional ``bedrock`` extra (``boto3``) can be imported.

    Used by diagnostics only; never as part of ``execute()``'s decision
    making (``resolve_client`` already reports a bounded
    ``dependency_unavailable`` error). Importing ``boto3`` reads no
    credentials and makes no network call.
    """

    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "CONVERSE_METHOD_NAME",
    "AwsAuthenticationError",
    "BedrockClientHandle",
    "BedrockRuntimeClient",
    "ClientResolution",
    "bedrock_extra_importable",
    "resolve_client",
]
