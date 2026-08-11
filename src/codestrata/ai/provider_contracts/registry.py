"""An explicit, deterministic ``AIProvider`` registry.

This is a **new, separate, unwired** registry — it is not
``codestrata.extensions.assess_ai.AssessAIProviderRegistry`` (the runtime
selection registry used by ``codestrata assess`` today) and it is not
``codestrata.ai.providers.registry.AIProviderRegistry`` (the Phase 5.8
embedding/answer knowledge registry). See ``relationship.py``.

Design:

* Construction is always explicit (``AIProviderRegistry()``); there is no
  process-wide default instance and no ``importlib.metadata`` entry-point
  discovery.
* ``register()`` takes a capability declaration and a zero-argument factory.
  Registering a provider **never** instantiates it — only ``resolve()``
  calls the factory, and only when a caller asks for that provider.
* ``register()`` rejects duplicate provider IDs.
* ``resolve()`` raises :class:`ProviderContractValidationError` for an
  unknown provider ID.
* ``list_provider_ids()`` always returns IDs in sorted order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.provider import AIProvider

ProviderFactory = Callable[[], AIProvider]


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """A static declaration of a provider's identity and declared capabilities."""

    provider_id: ProviderId
    capabilities: tuple[CapabilityId, ...]
    factory: ProviderFactory

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if not self.capabilities:
            raise ProviderContractValidationError(
                "capabilities must declare at least one CapabilityId"
            )
        for capability in self.capabilities:
            if not isinstance(capability, CapabilityId):
                raise ProviderContractValidationError(
                    f"capabilities must all be CapabilityId, got {type(capability).__name__}"
                )
        if not callable(self.factory):
            raise ProviderContractValidationError("factory must be callable")


class AIProviderRegistry:
    """In-process, explicitly constructed registry of provider registrations."""

    def __init__(self) -> None:
        self._registrations: dict[ProviderId, ProviderRegistration] = {}

    def register(self, registration: ProviderRegistration) -> None:
        if registration.provider_id in self._registrations:
            raise ProviderContractValidationError(
                f"provider already registered: {registration.provider_id.value}"
            )
        self._registrations[registration.provider_id] = registration

    def resolve(self, provider_id: ProviderId) -> AIProvider:
        registration = self._registrations.get(provider_id)
        if registration is None:
            known = [p.value for p in self.list_provider_ids()]
            raise ProviderContractValidationError(
                f"unknown provider: {provider_id!r}; registered: {known}"
            )
        return registration.factory()

    def list_provider_ids(self) -> tuple[ProviderId, ...]:
        return tuple(sorted(self._registrations, key=lambda p: p.value))

    def capabilities_for(self, provider_id: ProviderId) -> tuple[CapabilityId, ...]:
        registration = self._registrations.get(provider_id)
        if registration is None:
            raise ProviderContractValidationError(f"unknown provider: {provider_id}")
        return registration.capabilities

    def supports(self, provider_id: ProviderId, capability: CapabilityId) -> bool:
        return capability in self.capabilities_for(provider_id)


__all__ = [
    "AIProviderRegistry",
    "ProviderFactory",
    "ProviderRegistration",
]
