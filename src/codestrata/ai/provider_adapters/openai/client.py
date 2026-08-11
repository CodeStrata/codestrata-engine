"""The single credential boundary: lazy OpenAI client construction.

This is the **only** module in the adapter that reads ``os.environ`` or
imports the ``openai`` SDK, and it does both lazily — inside
:func:`resolve_client`, never at import time. Consequences:

* Importing the adapter package, asking it for its ``provider_id``, or asking
  ``supports()`` never touches credentials, the SDK, or the network.
* When AI enrichment is disabled, nothing here runs at all.
* Tests inject a client via ``injected_client=`` and never reach the SDK.

There is no process-wide client singleton. Each :func:`resolve_client` call
either returns the injected client or builds a fresh one, so no credential
state outlives a single invocation.

:func:`resolve_client` never raises for the two expected configuration
failures (extra not installed, API key not set) or for a client constructor
failure — it returns a :class:`ClientResolution` carrying a bounded
``AIProviderError`` instead, preserving the adapter's "``execute()`` never
raises for expected failures" contract (CR-3).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_adapters.openai.configuration import OpenAIClientInputs
from codestrata.ai.provider_contracts.errors import AIProviderError

EnvironmentReader = Callable[[str], str | None]


def default_environment_reader(name: str) -> str | None:
    """Read one environment variable. The approved credential-read boundary."""

    return os.environ.get(name)


@dataclass(frozen=True, slots=True)
class OpenAIClientHandle:
    """A constructed client plus the non-secret facts diagnostics may report.

    ``__repr__`` never renders the client object (whose own repr can echo a
    base URL or default headers), the base URL, or any credential.
    """

    client: Any
    api_key_env_name: str
    base_url_configured: bool
    injected: bool

    def __repr__(self) -> str:
        return (
            "OpenAIClientHandle("
            f"api_key_env_name={self.api_key_env_name!r}, "
            f"base_url_configured={self.base_url_configured}, "
            f"injected={self.injected}, "
            "client_present=True)"
        )


@dataclass(frozen=True, slots=True)
class ClientResolution:
    """Either a usable client handle or a bounded reason why there is none."""

    handle: OpenAIClientHandle | None = None
    error: AIProviderError | None = None
    legacy_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.handle is not None


def _failure(mapped: error_mapping.MappedFailure) -> ClientResolution:
    return ClientResolution(error=mapped.error, legacy_detail=mapped.legacy_detail)


def resolve_client(
    inputs: OpenAIClientInputs,
    *,
    injected_client: Any | None = None,
    environment_reader: EnvironmentReader = default_environment_reader,
) -> ClientResolution:
    """Return a client handle for ``inputs``, or a bounded error explaining why not."""

    base_url_configured = bool(inputs.base_url)
    if injected_client is not None:
        return ClientResolution(
            handle=OpenAIClientHandle(
                client=injected_client,
                api_key_env_name=inputs.api_key_env_name,
                base_url_configured=base_url_configured,
                injected=True,
            )
        )

    try:
        from openai import OpenAI
    except ImportError:
        return _failure(
            error_mapping.MappedFailure(
                error=error_mapping.build_error(error_mapping.CODE_MISSING_DEPENDENCY)
            )
        )

    api_key = (environment_reader(inputs.api_key_env_name) or "").strip()
    if not api_key:
        return _failure(
            error_mapping.MappedFailure(
                error=error_mapping.build_error(error_mapping.CODE_MISSING_API_KEY)
            )
        )

    kwargs: dict[str, Any] = {"api_key": api_key, "timeout": inputs.timeout_seconds}
    if inputs.base_url:
        kwargs["base_url"] = inputs.base_url
    try:
        client = OpenAI(**kwargs)
    except Exception as error:  # noqa: BLE001 - provider construction boundary
        return _failure(error_mapping.classify_client_construction_failure(error))

    return ClientResolution(
        handle=OpenAIClientHandle(
            client=client,
            api_key_env_name=inputs.api_key_env_name,
            base_url_configured=base_url_configured,
            injected=False,
        )
    )


def openai_extra_importable() -> bool:
    """Return whether the optional ``openai`` extra can be imported.

    Used by diagnostics only; never as part of ``execute()``'s decision
    making (``resolve_client`` already reports a bounded
    ``dependency_unavailable`` error).
    """

    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "ClientResolution",
    "EnvironmentReader",
    "OpenAIClientHandle",
    "default_environment_reader",
    "openai_extra_importable",
    "resolve_client",
]
