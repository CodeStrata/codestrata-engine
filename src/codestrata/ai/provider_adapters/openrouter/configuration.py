"""OpenRouter adapter configuration projection (Epic 11, Slice 11.10).

Projects ``OpenRouterSettings`` into privacy-preserving adapter configuration
plus private client inputs. Never stores API-key values. Never reads
``os.environ`` here — key presence is resolved only at the client boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from codestrata.ai.provider_contracts.adapter_configuration import (
    OpenRouterAdapterConfiguration,
    build_openrouter_adapter_configuration,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config.settings import OpenRouterSettings

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_API_KEY_ENV_NAME = "OPENROUTER_API_KEY"
_MAX_APP_NAME_LENGTH = 128
_MAX_SITE_URL_LENGTH = 2048


def validate_https_url(value: str, *, field_name: str) -> str:
    """Validate an HTTPS URL with no credentials, query, or fragment."""

    compact = value.strip()
    if not compact:
        raise ProviderContractValidationError(f"{field_name} must be a nonempty HTTPS URL")
    if len(compact) > _MAX_SITE_URL_LENGTH:
        raise ProviderContractValidationError(
            f"{field_name} must be at most {_MAX_SITE_URL_LENGTH} characters"
        )
    parsed = urlparse(compact)
    if parsed.scheme.lower() != "https":
        raise ProviderContractValidationError(f"{field_name} must use HTTPS")
    if parsed.username or parsed.password:
        raise ProviderContractValidationError(f"{field_name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ProviderContractValidationError(f"{field_name} must not contain a query or fragment")
    if not parsed.netloc:
        raise ProviderContractValidationError(f"{field_name} must include a host")
    return compact.rstrip("/")


def normalize_base_url(value: str | None) -> str:
    """Resolve and validate the OpenRouter API base URL."""

    candidate = (value or "").strip() or OPENROUTER_DEFAULT_BASE_URL
    return validate_https_url(candidate, field_name="base_url")


@dataclass(frozen=True, slots=True)
class OpenRouterClientInputs:
    """Private inputs required to construct an OpenRouter-compatible client.

    ``__repr__`` never renders the base URL, site URL, app name, or any secret.
    """

    api_key_env_name: str
    base_url: str
    timeout_seconds: float
    site_url: str | None = None
    app_name: str | None = None

    def __repr__(self) -> str:
        return (
            "OpenRouterClientInputs("
            f"api_key_env_name={self.api_key_env_name!r}, "
            f"base_url_configured={bool(self.base_url)}, "
            f"site_url_configured={bool(self.site_url)}, "
            f"app_name_configured={bool(self.app_name)}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


@dataclass(frozen=True, slots=True)
class OpenRouterRuntimeConfiguration:
    """Adapter configuration plus private client inputs."""

    adapter_configuration: OpenRouterAdapterConfiguration
    client_inputs: OpenRouterClientInputs

    @property
    def api_key_env_name(self) -> str:
        return self.client_inputs.api_key_env_name

    def __repr__(self) -> str:
        return f"OpenRouterRuntimeConfiguration(client_inputs={self.client_inputs!r})"

    def redacted(self) -> dict[str, object]:
        view = dict(self.adapter_configuration.redacted())
        view["timeout_seconds"] = self.client_inputs.timeout_seconds
        return view


def resolve_api_key_env_name(openrouter_settings: OpenRouterSettings | None) -> str:
    if openrouter_settings is None:
        return DEFAULT_API_KEY_ENV_NAME
    return (openrouter_settings.api_key_env or "").strip() or DEFAULT_API_KEY_ENV_NAME


def resolve_optional_site_url(openrouter_settings: OpenRouterSettings | None) -> str | None:
    if openrouter_settings is None:
        return None
    compact = (openrouter_settings.site_url or "").strip()
    if not compact:
        return None
    return validate_https_url(compact, field_name="site_url")


def resolve_optional_app_name(openrouter_settings: OpenRouterSettings | None) -> str | None:
    if openrouter_settings is None:
        return None
    compact = (openrouter_settings.app_name or "").strip()
    if not compact:
        return None
    if len(compact) > _MAX_APP_NAME_LENGTH:
        raise ProviderContractValidationError(
            f"app_name must be at most {_MAX_APP_NAME_LENGTH} characters"
        )
    return compact


def build_runtime_configuration(
    *,
    openrouter_settings: OpenRouterSettings | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_key_present: bool = False,
    base_url: str | None = None,
    max_retries: int | None = None,
) -> OpenRouterRuntimeConfiguration:
    """Project settings into adapter configuration plus client inputs (no env reads)."""

    api_key_env_name = resolve_api_key_env_name(openrouter_settings)
    if base_url is not None:
        resolved_base = normalize_base_url(base_url)
    elif openrouter_settings is not None and (openrouter_settings.base_url or "").strip():
        resolved_base = normalize_base_url(openrouter_settings.base_url)
    else:
        resolved_base = normalize_base_url(OPENROUTER_DEFAULT_BASE_URL)

    site_url = resolve_optional_site_url(openrouter_settings)
    app_name = resolve_optional_app_name(openrouter_settings)
    resolved_max_retries = max_retries
    if resolved_max_retries is None and openrouter_settings is not None:
        resolved_max_retries = openrouter_settings.max_retries

    adapter_configuration = build_openrouter_adapter_configuration(
        api_key_env_name=api_key_env_name,
        api_key_present=api_key_present,
        base_url=resolved_base,
        base_url_configured=True,
        site_url_configured=site_url is not None,
        app_name_configured=app_name is not None,
        max_retries=resolved_max_retries,
    )
    return OpenRouterRuntimeConfiguration(
        adapter_configuration=adapter_configuration,
        client_inputs=OpenRouterClientInputs(
            api_key_env_name=api_key_env_name,
            base_url=resolved_base,
            timeout_seconds=float(timeout_seconds),
            site_url=site_url,
            app_name=app_name,
        ),
    )


__all__ = [
    "DEFAULT_API_KEY_ENV_NAME",
    "OPENROUTER_DEFAULT_BASE_URL",
    "OpenRouterClientInputs",
    "OpenRouterRuntimeConfiguration",
    "build_runtime_configuration",
    "normalize_base_url",
    "resolve_api_key_env_name",
    "resolve_optional_app_name",
    "resolve_optional_site_url",
    "validate_https_url",
]
