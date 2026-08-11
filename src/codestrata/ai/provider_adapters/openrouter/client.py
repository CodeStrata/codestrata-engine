"""Lazy OpenRouter client construction at the single credential boundary.

This is the **only** OpenRouter adapter module that reads ``os.environ`` or
imports the OpenAI-compatible SDK, and it does both lazily inside
:func:`resolve_client`. Capability discovery and package import never touch
credentials or the network.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_adapters.openrouter import error_mapping
from codestrata.ai.provider_adapters.openrouter.configuration import OpenRouterClientInputs
from codestrata.ai.provider_contracts.errors import AIProviderError

EnvironmentReader = Callable[[str], str | None]


def default_environment_reader(name: str) -> str | None:
    """Read one environment variable. The approved credential-read boundary."""

    return os.environ.get(name)


@dataclass(frozen=True, slots=True)
class OpenRouterClientHandle:
    """A constructed client plus non-secret facts diagnostics may report."""

    client: Any
    api_key_env_name: str
    base_url_configured: bool
    injected: bool

    def __repr__(self) -> str:
        return (
            "OpenRouterClientHandle("
            f"api_key_env_name={self.api_key_env_name!r}, "
            f"base_url_configured={self.base_url_configured}, "
            f"injected={self.injected}, "
            "client_present=True)"
        )


@dataclass(frozen=True, slots=True)
class ClientResolution:
    """Either a usable client handle or a bounded reason why there is none."""

    handle: OpenRouterClientHandle | None = None
    error: AIProviderError | None = None
    legacy_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.handle is not None


def _failure(mapped: error_mapping.MappedFailure) -> ClientResolution:
    return ClientResolution(error=mapped.error, legacy_detail=mapped.legacy_detail)


def _optional_default_headers(inputs: OpenRouterClientInputs) -> dict[str, str]:
    headers: dict[str, str] = {}
    if inputs.site_url:
        headers["HTTP-Referer"] = inputs.site_url
    if inputs.app_name:
        headers["X-Title"] = inputs.app_name
    return headers


def resolve_client(
    inputs: OpenRouterClientInputs,
    *,
    injected_client: Any | None = None,
    environment_reader: EnvironmentReader = default_environment_reader,
) -> ClientResolution:
    """Return a client handle for ``inputs``, or a bounded error explaining why not."""

    base_url_configured = bool(inputs.base_url)
    if injected_client is not None:
        return ClientResolution(
            handle=OpenRouterClientHandle(
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

    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": inputs.base_url,
        "timeout": inputs.timeout_seconds,
    }
    headers = _optional_default_headers(inputs)
    if headers:
        kwargs["default_headers"] = headers
    try:
        client = OpenAI(**kwargs)
    except Exception as error:  # noqa: BLE001
        return _failure(error_mapping.classify_client_construction_failure(error))

    return ClientResolution(
        handle=OpenRouterClientHandle(
            client=client,
            api_key_env_name=inputs.api_key_env_name,
            base_url_configured=base_url_configured,
            injected=False,
        )
    )


def openai_compatible_extra_importable() -> bool:
    """Return whether the optional OpenAI-compatible SDK can be imported."""

    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "ClientResolution",
    "EnvironmentReader",
    "OpenRouterClientHandle",
    "default_environment_reader",
    "openai_compatible_extra_importable",
    "resolve_client",
]
