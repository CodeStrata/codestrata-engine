"""Unit tests for provider_contracts.registry."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.registry import AIProviderRegistry, ProviderRegistration
from tests.ai.provider_contracts.fakes import FakeFailingProvider, FakeSucceedingProvider


def _registration(
    provider_id: ProviderId = ProviderId.OPENAI, *, instantiated: list[str] | None = None
) -> ProviderRegistration:
    log = instantiated if instantiated is not None else []

    def factory() -> FakeSucceedingProvider:
        log.append(provider_id.value)
        return FakeSucceedingProvider(provider_id=provider_id)

    return ProviderRegistration(
        provider_id=provider_id,
        capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
        factory=factory,
    )


def test_construction_is_always_explicit() -> None:
    registry = AIProviderRegistry()
    assert registry.list_provider_ids() == ()


def test_register_and_resolve_roundtrip() -> None:
    registry = AIProviderRegistry()
    registry.register(_registration(ProviderId.OPENAI))
    provider = registry.resolve(ProviderId.OPENAI)
    assert provider.provider_id is ProviderId.OPENAI


def test_register_rejects_duplicate_provider_id() -> None:
    registry = AIProviderRegistry()
    registry.register(_registration(ProviderId.OPENAI))
    with pytest.raises(ProviderContractValidationError):
        registry.register(_registration(ProviderId.OPENAI))


def test_resolve_raises_for_unknown_provider_id() -> None:
    registry = AIProviderRegistry()
    with pytest.raises(ProviderContractValidationError):
        registry.resolve(ProviderId.BEDROCK)


def test_list_provider_ids_is_sorted() -> None:
    registry = AIProviderRegistry()
    registry.register(_registration(ProviderId.OPENAI))
    registry.register(_registration(ProviderId.BEDROCK))
    assert registry.list_provider_ids() == (ProviderId.BEDROCK, ProviderId.OPENAI)


def test_capability_query_uses_static_declarations() -> None:
    registry = AIProviderRegistry()
    registry.register(_registration(ProviderId.OPENAI))
    assert registry.capabilities_for(ProviderId.OPENAI) == (CapabilityId.MODERNIZATION_ADVISOR,)
    assert registry.supports(ProviderId.OPENAI, CapabilityId.MODERNIZATION_ADVISOR) is True


def test_registration_never_instantiates_the_provider() -> None:
    instantiated: list[str] = []
    registry = AIProviderRegistry()
    registry.register(_registration(ProviderId.OPENAI, instantiated=instantiated))
    assert instantiated == []
    registry.resolve(ProviderId.OPENAI)
    assert instantiated == ["openai"]


def test_registration_requires_at_least_one_capability() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderRegistration(
            provider_id=ProviderId.OPENAI,
            capabilities=(),
            factory=FakeFailingProvider,
        )


def test_registration_requires_callable_factory() -> None:
    with pytest.raises(ProviderContractValidationError):
        ProviderRegistration(
            provider_id=ProviderId.OPENAI,
            capabilities=(CapabilityId.MODERNIZATION_ADVISOR,),
            factory="not-callable",  # type: ignore[arg-type]
        )
