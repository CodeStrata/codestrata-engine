"""Registry-backed assess / Modernization Advisor AI providers."""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points

from codestrata.ai.providers.base import AIModelProvider
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from codestrata.config.settings import CodestrataSettings
from codestrata.extensions.version import EXTENSION_API_VERSION, extension_api_compatible

AssessProviderFactory = Callable[[CodestrataSettings], AIModelProvider]

ENTRY_POINT_GROUP = "codestrata.assess_ai_provider_extensions"


class AssessAIProviderRegistry:
    """In-process registry of assess AI provider factories."""

    def __init__(self) -> None:
        self._factories: dict[str, AssessProviderFactory] = {}
        self._api_versions: dict[str, str] = {}

    def register(
        self,
        name: str,
        factory: AssessProviderFactory,
        *,
        api_version: str = EXTENSION_API_VERSION,
    ) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("assess AI provider name must be nonempty")
        if not extension_api_compatible(api_version):
            raise ValueError(
                f"assess AI provider {key!r} declares incompatible Extension API "
                f"{api_version!r} (Engine speaks {EXTENSION_API_VERSION})"
            )
        if key in self._factories:
            raise ValueError(f"assess AI provider already registered: {key}")
        self._factories[key] = factory
        self._api_versions[key] = api_version

    def create(self, name: str, settings: CodestrataSettings) -> AIModelProvider:
        key = name.strip().lower()
        if key not in self._factories:
            raise AIProviderConfigurationError(
                f"Unsupported assess AI provider '{name}'. "
                f"Registered: {', '.join(self.list_providers()) or '(none)'}."
            )
        return self._factories[key](settings)

    def list_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def api_version_for(self, name: str) -> str | None:
        return self._api_versions.get(name.strip().lower())


_DEFAULT: AssessAIProviderRegistry | None = None


def get_assess_ai_provider_registry() -> AssessAIProviderRegistry:
    """Return the process-wide assess provider registry (bootstrapped once)."""

    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AssessAIProviderRegistry()
        _bootstrap_assess_providers(_DEFAULT)
    return _DEFAULT


def reset_assess_ai_provider_registry_for_tests() -> None:
    """Clear the default assess provider registry (tests only)."""

    global _DEFAULT
    _DEFAULT = None


def _bootstrap_assess_providers(registry: AssessAIProviderRegistry) -> None:
    def _bedrock(settings: CodestrataSettings) -> AIModelProvider:
        from codestrata.ai.providers.bedrock import BedrockAIModelProvider

        return BedrockAIModelProvider(settings=settings)

    def _openai(settings: CodestrataSettings) -> AIModelProvider:
        from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider

        return OpenAIAIModelProvider(settings=settings)

    registry.register("bedrock", _bedrock, api_version=EXTENSION_API_VERSION)
    registry.register("openai", _openai, api_version=EXTENSION_API_VERSION)

    for ep in entry_points().select(group=ENTRY_POINT_GROUP):
        try:
            loaded = ep.load()
        except Exception:  # noqa: BLE001 - optional surface
            continue
        if callable(loaded) and not hasattr(loaded, "id"):
            # Registrar style: register(registry) -> None
            try:
                loaded(registry)
            except Exception:  # noqa: BLE001
                continue
            continue
        # Extension instance style
        try:
            extension_id = str(loaded.id)
            api_version = str(getattr(loaded, "api_version", EXTENSION_API_VERSION))
            create = loaded.create
        except Exception:  # noqa: BLE001
            continue
        if not callable(create):
            continue
        try:
            registry.register(extension_id, create, api_version=api_version)
        except ValueError:
            continue


__all__ = [
    "ENTRY_POINT_GROUP",
    "AssessAIProviderRegistry",
    "AssessProviderFactory",
    "get_assess_ai_provider_registry",
    "reset_assess_ai_provider_registry_for_tests",
]
