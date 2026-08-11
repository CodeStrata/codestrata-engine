"""Unit tests for provider_contracts.provider (the AIProvider protocol)."""

from __future__ import annotations

import inspect

from codestrata.ai.provider_contracts.provider import CONTRACT_MEMBER_NAMES, AIProvider
from tests.ai.provider_contracts.fakes import FakeSucceedingProvider


def test_contract_member_names_are_exactly_three() -> None:
    assert CONTRACT_MEMBER_NAMES == frozenset({"provider_id", "supports", "execute"})


def test_protocol_declares_no_async_streaming_or_configuration_members() -> None:
    protocol_members = {
        name for name, _ in inspect.getmembers(AIProvider) if not name.startswith("_")
    }
    forbidden = {
        "configure",
        "set_api_key",
        "client",
        "raw_client",
        "stream",
        "astream",
        "aexecute",
        "tools",
        "bind_tools",
    }
    assert protocol_members.isdisjoint(forbidden)


def test_fake_provider_satisfies_the_runtime_checkable_protocol() -> None:
    fake = FakeSucceedingProvider()
    assert isinstance(fake, AIProvider)


def test_execute_is_synchronous_not_a_coroutine_function() -> None:
    fake = FakeSucceedingProvider()
    assert not inspect.iscoroutinefunction(fake.execute)
