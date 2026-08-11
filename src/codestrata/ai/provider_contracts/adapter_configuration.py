"""Type-safe, privacy-preserving per-provider adapter configuration.

``OpenAIAdapterConfiguration`` and ``BedrockAdapterConfiguration`` represent,
as immutable value objects, exactly the settings fields Slice 11.3's ground
truth says are actually used on the assess path today:

* OpenAI: ``api_key_env`` (the *name* of an environment variable, never its
  value), an optional ``base_url``, and ``answer_model`` (represented
  separately, on ``AIProviderConfiguration.model_reference``).
* Bedrock: ``model_id`` (likewise represented on ``model_reference``),
  ``aws.profile``/``aws.region``/``ai.bedrock.region`` (represented here as
  presence booleans only — never as the actual profile name or region
  string, which are credential-adjacent).

Neither type invents fields that do not exist on the real settings model
(no ``organization``, ``project``, or Bedrock ``endpoint_url`` — Slice
11.3's ground truth confirms none of these exist today). ``max_retries`` is
carried as an optional int purely to *represent* the corresponding settings
field (``BedrockSettings.max_retries`` / ``OpenAISettings.max_retries``) —
carrying it here is not a claim that it is wired to anything; see
``compatibility.py``/CR-2 and ``docs/ai-provider-configuration.md``.

``OpenAIAdapterConfiguration.base_url`` is the **one** private, non-secret
field in this module that is not reducible to a boolean: it is stored
opaquely for potential future adapter construction, but ``.redacted()`` (and
every diagnostics/serialization path) never emits its value — only
``base_url_configured: bool``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId

_MAX_ENV_NAME_LENGTH = 128
_MAX_BASE_URL_LENGTH = 2048


def _validate_optional_non_negative_int(value: int | None, *, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ProviderContractValidationError(f"{field_name} must be a non-negative int or None")


@dataclass(frozen=True, slots=True)
class OpenAIAdapterConfiguration:
    """Privacy-preserving representation of the OpenAI-specific settings surface.

    ``api_key_env_name`` is the *name* of the environment variable that
    would supply the API key (e.g. ``"OPENAI_API_KEY"``) — never the key
    value itself. ``base_url`` is stored opaquely (for potential future
    adapter construction) but is never emitted by ``.redacted()`` or any
    diagnostics/serialization helper.
    """

    api_key_env_name: str | None = None
    api_key_present: bool = False
    base_url: str | None = None
    base_url_configured: bool = False
    max_retries: int | None = None

    def __post_init__(self) -> None:
        if self.api_key_env_name is not None:
            if not isinstance(self.api_key_env_name, str) or not self.api_key_env_name.strip():
                raise ProviderContractValidationError(
                    "api_key_env_name must be a non-empty string when present"
                )
            if len(self.api_key_env_name) > _MAX_ENV_NAME_LENGTH:
                raise ProviderContractValidationError(
                    f"api_key_env_name must be at most {_MAX_ENV_NAME_LENGTH} characters"
                )
        if not isinstance(self.api_key_present, bool):
            raise ProviderContractValidationError("api_key_present must be a bool")
        if self.base_url is not None:
            if not isinstance(self.base_url, str):
                raise ProviderContractValidationError("base_url must be a string when present")
            if len(self.base_url) > _MAX_BASE_URL_LENGTH:
                raise ProviderContractValidationError(
                    f"base_url must be at most {_MAX_BASE_URL_LENGTH} characters"
                )
        if not isinstance(self.base_url_configured, bool):
            raise ProviderContractValidationError("base_url_configured must be a bool")
        if self.base_url and self.base_url.strip() and not self.base_url_configured:
            raise ProviderContractValidationError(
                "a non-blank base_url requires base_url_configured=True"
            )
        # NOTE: the reverse is intentionally NOT required — base_url_configured
        # may be True while base_url is None. Callers that only know "a
        # base_url is configured" (a boolean, e.g. from LegacyConfigurationInput.
        # openai_base_url_configured) without ever holding the actual URL value
        # are the privacy-preferred path; storing the raw value is optional.
        _validate_optional_non_negative_int(self.max_retries, field_name="max_retries")

    def redacted(self) -> dict[str, Any]:
        """Return a diagnostics-safe view: presence booleans and the env var name only.

        Never includes ``base_url``'s value — only whether one is configured.
        """

        return {
            "adapter_kind": "openai",
            "api_key_env_name": self.api_key_env_name,
            "api_key_present": self.api_key_present,
            "base_url_configured": self.base_url_configured,
            "max_retries_declared": self.max_retries is not None,
        }


@dataclass(frozen=True, slots=True)
class BedrockAdapterConfiguration:
    """Privacy-preserving representation of the Bedrock-specific settings surface.

    ``region_configured``/``profile_configured`` are presence booleans only
    — the actual region string and AWS profile name are credential-adjacent
    and are never carried by this value object. There is no ``endpoint_url``
    field: Slice 11.3's ground truth confirms Bedrock has no configurable
    endpoint override today.
    """

    region_configured: bool = False
    profile_configured: bool = False
    max_retries: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.region_configured, bool):
            raise ProviderContractValidationError("region_configured must be a bool")
        if not isinstance(self.profile_configured, bool):
            raise ProviderContractValidationError("profile_configured must be a bool")
        _validate_optional_non_negative_int(self.max_retries, field_name="max_retries")

    def redacted(self) -> dict[str, Any]:
        """Return a diagnostics-safe view: presence booleans only."""

        return {
            "adapter_kind": "bedrock",
            "max_retries_declared": self.max_retries is not None,
            "profile_configured": self.profile_configured,
            "region_configured": self.region_configured,
        }


@dataclass(frozen=True, slots=True)
class OpenRouterAdapterConfiguration:
    """Privacy-preserving representation of the OpenRouter adapter settings surface.

    Slice 11.10 stores only the API-key environment-variable *name* and presence
    flags — never the key value. ``base_url`` may be held privately for client
    construction but is never emitted by :meth:`redacted`. Optional site URL /
    app name are presence-only in diagnostics.
    """

    api_key_env_name: str | None = None
    api_key_present: bool = False
    base_url: str | None = None
    base_url_configured: bool = False
    site_url_configured: bool = False
    app_name_configured: bool = False
    max_retries: int | None = None

    def __post_init__(self) -> None:
        if self.api_key_env_name is not None:
            if not isinstance(self.api_key_env_name, str) or not self.api_key_env_name.strip():
                raise ProviderContractValidationError(
                    "api_key_env_name must be a non-empty string when present"
                )
            if len(self.api_key_env_name) > _MAX_ENV_NAME_LENGTH:
                raise ProviderContractValidationError(
                    f"api_key_env_name must be at most {_MAX_ENV_NAME_LENGTH} characters"
                )
        if not isinstance(self.api_key_present, bool):
            raise ProviderContractValidationError("api_key_present must be a bool")
        if self.base_url is not None:
            if not isinstance(self.base_url, str):
                raise ProviderContractValidationError("base_url must be a string when present")
            if len(self.base_url) > _MAX_BASE_URL_LENGTH:
                raise ProviderContractValidationError(
                    f"base_url must be at most {_MAX_BASE_URL_LENGTH} characters"
                )
        if not isinstance(self.base_url_configured, bool):
            raise ProviderContractValidationError("base_url_configured must be a bool")
        if self.base_url and self.base_url.strip() and not self.base_url_configured:
            raise ProviderContractValidationError(
                "a non-blank base_url requires base_url_configured=True"
            )
        if not isinstance(self.site_url_configured, bool):
            raise ProviderContractValidationError("site_url_configured must be a bool")
        if not isinstance(self.app_name_configured, bool):
            raise ProviderContractValidationError("app_name_configured must be a bool")
        _validate_optional_non_negative_int(self.max_retries, field_name="max_retries")

    def redacted(self) -> dict[str, Any]:
        """Return a diagnostics-safe view: presence booleans and env-var name only."""

        return {
            "adapter_kind": "openrouter",
            "api_key_env_name": self.api_key_env_name,
            "api_key_present": self.api_key_present,
            "app_name_configured": self.app_name_configured,
            "base_url_configured": self.base_url_configured,
            "max_retries_declared": self.max_retries is not None,
            "site_url_configured": self.site_url_configured,
        }


AdapterConfiguration = (
    OpenAIAdapterConfiguration | BedrockAdapterConfiguration | OpenRouterAdapterConfiguration
)

# Maps each ProviderId to the adapter configuration type that must be paired
# with it on AIProviderConfiguration.adapter_configuration.
ADAPTER_CONFIGURATION_TYPES_BY_PROVIDER: dict[ProviderId, type] = {
    ProviderId.OPENAI: OpenAIAdapterConfiguration,
    ProviderId.BEDROCK: BedrockAdapterConfiguration,
    ProviderId.OPENROUTER: OpenRouterAdapterConfiguration,
}


def validate_adapter_matches_provider(
    provider_id: ProviderId, adapter_configuration: AdapterConfiguration
) -> None:
    """Raise if ``adapter_configuration``'s type does not match ``provider_id``.

    This is the "type-safe; mismatch reject" invariant: an
    ``OpenAIAdapterConfiguration`` may never be paired with
    ``ProviderId.BEDROCK`` and vice versa.
    """

    expected_type = ADAPTER_CONFIGURATION_TYPES_BY_PROVIDER.get(provider_id)
    if expected_type is None or not isinstance(adapter_configuration, expected_type):
        raise ProviderContractValidationError(
            f"adapter_configuration type {type(adapter_configuration).__name__} does not match "
            f"provider_id {provider_id!r} (expected {getattr(expected_type, '__name__', None)})"
        )


def build_openai_adapter_configuration(
    *,
    api_key_env_name: str | None,
    api_key_present: bool,
    base_url: str | None = None,
    base_url_configured: bool | None = None,
    max_retries: int | None = None,
) -> OpenAIAdapterConfiguration:
    """Build an ``OpenAIAdapterConfiguration``.

    When ``base_url`` is given, ``base_url_configured`` is derived from it
    (unless explicitly overridden). When only ``base_url_configured`` is
    known (the privacy-preferred path — e.g. from
    ``LegacyConfigurationInput.openai_base_url_configured``, which never
    carries the raw URL), pass it directly and leave ``base_url`` unset.
    """

    compact_base_url = base_url.strip() if isinstance(base_url, str) else None
    resolved_configured = (
        bool(compact_base_url) if base_url_configured is None else bool(base_url_configured)
    )
    return OpenAIAdapterConfiguration(
        api_key_env_name=api_key_env_name,
        api_key_present=api_key_present,
        base_url=compact_base_url or None,
        base_url_configured=resolved_configured,
        max_retries=max_retries,
    )


def build_bedrock_adapter_configuration(
    *,
    region_configured: bool,
    profile_configured: bool,
    max_retries: int | None = None,
) -> BedrockAdapterConfiguration:
    """Build a ``BedrockAdapterConfiguration`` from presence booleans only."""

    return BedrockAdapterConfiguration(
        region_configured=region_configured,
        profile_configured=profile_configured,
        max_retries=max_retries,
    )


def build_openrouter_adapter_configuration(
    *,
    api_key_env_name: str | None = None,
    api_key_present: bool = False,
    base_url: str | None = None,
    base_url_configured: bool | None = None,
    site_url_configured: bool = False,
    app_name_configured: bool = False,
    max_retries: int | None = None,
) -> OpenRouterAdapterConfiguration:
    """Build an ``OpenRouterAdapterConfiguration`` without reading credentials."""

    if base_url_configured is None:
        base_url_configured = bool(base_url and base_url.strip())
    return OpenRouterAdapterConfiguration(
        api_key_env_name=api_key_env_name,
        api_key_present=api_key_present,
        base_url=base_url,
        base_url_configured=base_url_configured,
        site_url_configured=site_url_configured,
        app_name_configured=app_name_configured,
        max_retries=max_retries,
    )


__all__ = [
    "ADAPTER_CONFIGURATION_TYPES_BY_PROVIDER",
    "AdapterConfiguration",
    "BedrockAdapterConfiguration",
    "OpenAIAdapterConfiguration",
    "OpenRouterAdapterConfiguration",
    "build_bedrock_adapter_configuration",
    "build_openai_adapter_configuration",
    "build_openrouter_adapter_configuration",
    "validate_adapter_matches_provider",
]
