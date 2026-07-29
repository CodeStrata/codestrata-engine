"""Language evidence provider registry."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from codestrata.domain.evidence.language.contracts import (
    LanguageEvidenceProvider,
    LanguageEvidenceProviderMetadata,
)
from codestrata.domain.evidence.language.errors import LanguageEvidenceRegistryError


class LanguageEvidenceProviderRegistry:
    """Explicit registration only — no dynamic imports or plugins."""

    def __init__(self) -> None:
        self._providers: dict[str, LanguageEvidenceProvider] = {}

    def register(self, provider: LanguageEvidenceProvider) -> None:
        metadata = provider.metadata
        provider_id = str(metadata.provider_id)
        existing = self._providers.get(provider_id)
        if existing is not None:
            if existing.metadata.provider_version != metadata.provider_version:
                raise LanguageEvidenceRegistryError(
                    f"Conflicting versions for provider {provider_id}: "
                    f"{existing.metadata.provider_version} vs {metadata.provider_version}",
                    reason_code="conflicting_provider_version",
                    provider_id=provider_id,
                )
            raise LanguageEvidenceRegistryError(
                f"Duplicate provider ID: {provider_id}",
                reason_code="duplicate_provider_id",
                provider_id=provider_id,
            )
        self._providers[provider_id] = provider

    def register_collection(
        self,
        providers: Sequence[LanguageEvidenceProvider] | Iterable[LanguageEvidenceProvider],
    ) -> None:
        for provider in providers:
            self.register(provider)

    def get(self, provider_id: str) -> LanguageEvidenceProvider:
        key = provider_id.strip().lower()
        provider = self._providers.get(key)
        if provider is None:
            raise LanguageEvidenceRegistryError(
                f"Unknown provider: {provider_id}",
                reason_code="provider_not_found",
                provider_id=provider_id,
            )
        return provider

    def list_providers(
        self,
        *,
        language: str | None = None,
        capability: str | None = None,
    ) -> tuple[LanguageEvidenceProviderMetadata, ...]:
        items: list[LanguageEvidenceProviderMetadata] = []
        for provider_id in sorted(self._providers):
            meta = self._providers[provider_id].metadata
            if language is not None:
                lang = language.strip().lower()
                if lang not in meta.supported_languages:
                    continue
            if capability is not None:
                cap = capability.strip().lower()
                supported = meta.capabilities.supported_ids()
                if cap not in supported:
                    continue
            items.append(meta)
        return tuple(items)

    def list_by_language(self, language: str) -> tuple[LanguageEvidenceProviderMetadata, ...]:
        return self.list_providers(language=language)

    def list_by_capability(self, capability: str) -> tuple[LanguageEvidenceProviderMetadata, ...]:
        return self.list_providers(capability=capability)

    def explain_selection(self) -> dict[str, object]:
        return {
            "provider_count": len(self._providers),
            "provider_ids": sorted(self._providers),
            "ordering": "lexical_by_provider_id",
        }

    @property
    def size(self) -> int:
        return len(self._providers)

    def providers(self) -> tuple[LanguageEvidenceProvider, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))
