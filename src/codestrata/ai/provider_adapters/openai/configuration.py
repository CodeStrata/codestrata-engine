"""Bridge ``OpenAISettings`` into contract configuration plus runtime client inputs.

Two distinct shapes come out of this module:

* :class:`~codestrata.ai.provider_contracts.adapter_configuration.
  OpenAIAdapterConfiguration` — the privacy-preserving Slice 11.3 value
  object used for diagnostics. Its ``.redacted()`` view never carries the
  base URL value or the API key.
* :class:`OpenAIClientInputs` — the *private* values ``client.py`` needs to
  actually construct a client: the name of the API key environment variable,
  the optional base URL, and the request timeout in seconds.

Nothing here reads ``os.environ``, opens a file, or constructs a client.
``api_key_present`` is therefore ``False`` unless a caller explicitly tells
us otherwise: key presence is only ever resolved at the single credential
boundary in ``client.py``.

Config keys are unchanged from the pre-migration provider: ``api_key_env``
(default ``OPENAI_API_KEY``), ``base_url``, and ``answer_model`` (resolved
outside this module by ``codestrata.ai.providers.factory``).
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.adapter_configuration import (
    OpenAIAdapterConfiguration,
    build_openai_adapter_configuration,
)
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import OpenAISettings

DEFAULT_API_KEY_ENV_NAME = "OPENAI_API_KEY"


@dataclass(frozen=True, slots=True)
class OpenAIClientInputs:
    """The private inputs required to construct an OpenAI client.

    ``__repr__`` is redacted: the base URL is a deployment detail (it can
    point at a private gateway) and is never rendered, only its presence.
    """

    api_key_env_name: str
    base_url: str | None
    timeout_seconds: float

    def __repr__(self) -> str:
        return (
            "OpenAIClientInputs("
            f"api_key_env_name={self.api_key_env_name!r}, "
            f"base_url_configured={self.base_url is not None}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class OpenAIRuntimeConfiguration:
    """Everything the adapter needs from configuration, split by privacy class.

    ``__repr__`` is redacted rather than inherited: the nested
    ``OpenAIAdapterConfiguration`` retains the base URL *value* (Slice 11.3
    keeps it for callers that need it and redacts only in ``.redacted()``), so
    a default dataclass repr would render a private gateway URL into anything
    that logs this object.
    """

    adapter_configuration: OpenAIAdapterConfiguration
    client_inputs: OpenAIClientInputs

    @property
    def api_key_env_name(self) -> str:
        return self.client_inputs.api_key_env_name

    def __repr__(self) -> str:
        return f"OpenAIRuntimeConfiguration(client_inputs={self.client_inputs!r})"

    def redacted(self) -> dict[str, object]:
        """Return a diagnostics-safe view (presence booleans and the env var name)."""

        view = dict(self.adapter_configuration.redacted())
        view["timeout_seconds"] = self.client_inputs.timeout_seconds
        return view


def resolve_api_key_env_name(openai_settings: OpenAISettings | None) -> str:
    """Resolve the API key environment variable *name* (never its value)."""

    if openai_settings is None:
        return DEFAULT_API_KEY_ENV_NAME
    return (openai_settings.api_key_env or "").strip() or DEFAULT_API_KEY_ENV_NAME


def resolve_base_url(openai_settings: OpenAISettings | None) -> str | None:
    """Resolve the optional base URL override, normalizing blank to ``None``."""

    if openai_settings is None:
        return None
    compact = (openai_settings.base_url or "").strip()
    return compact or None


def build_runtime_configuration(
    *,
    openai_settings: OpenAISettings | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_key_present: bool = False,
) -> OpenAIRuntimeConfiguration:
    """Project ``OpenAISettings`` into adapter configuration plus client inputs."""

    api_key_env_name = resolve_api_key_env_name(openai_settings)
    base_url = resolve_base_url(openai_settings)
    max_retries = getattr(openai_settings, "max_retries", None) if openai_settings else None
    adapter_configuration = build_openai_adapter_configuration(
        api_key_env_name=api_key_env_name,
        api_key_present=api_key_present,
        base_url=base_url,
        max_retries=max_retries,
    )
    return OpenAIRuntimeConfiguration(
        adapter_configuration=adapter_configuration,
        client_inputs=OpenAIClientInputs(
            api_key_env_name=api_key_env_name,
            base_url=base_url,
            timeout_seconds=float(timeout_seconds),
        ),
    )


__all__ = [
    "DEFAULT_API_KEY_ENV_NAME",
    "OpenAIClientInputs",
    "OpenAIRuntimeConfiguration",
    "build_runtime_configuration",
    "resolve_api_key_env_name",
    "resolve_base_url",
]
