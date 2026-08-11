"""The ``AIProvider`` protocol.

Deliberately minimal and synchronous: three members, no more. There is no
``async``/streaming/tool-calling support, and no ``configure()``/
``set_api_key()``/raw-client accessor — those concerns belong to whatever
constructs a concrete provider (a factory), not to the contract itself.

This protocol is **not** implemented by any production provider in Slice
11.2. See ``relationship.py`` for how it relates to the existing
``codestrata.ai.providers.base.AIModelProvider`` ABC, which remains the
production abstraction for ``codestrata assess``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest
from codestrata.ai.provider_contracts.responses import AIProviderResult

# The exact, closed set of members an AIProvider implementation may expose as
# part of this contract. Used by tests to assert fakes stay minimal; this is
# documentation of intent, not a runtime enforcement mechanism (Protocol
# structural typing does not forbid additional methods on a concrete class).
CONTRACT_MEMBER_NAMES: frozenset[str] = frozenset({"provider_id", "supports", "execute"})


@runtime_checkable
class AIProvider(Protocol):
    """Synchronous provider contract: identify, declare, execute."""

    @property
    def provider_id(self) -> ProviderId:
        """The stable identifier of this provider."""
        ...

    def supports(self, capability: CapabilityId) -> bool:
        """Return whether this provider declares support for ``capability``."""
        ...

    def execute(self, request: AIProviderRequest) -> AIProviderResult:
        """Execute a single request synchronously and return a result.

        Implementations must never raise for provider/parsing/validation
        failures that are expected in normal operation — those must be
        represented as a ``FAILED``/``UNAVAILABLE`` :class:`AIProviderResult`
        instead, preserving fail-soft semantics (CR-3).
        """
        ...


__all__ = [
    "CONTRACT_MEMBER_NAMES",
    "AIProvider",
]
