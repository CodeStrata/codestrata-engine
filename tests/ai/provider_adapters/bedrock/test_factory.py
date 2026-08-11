"""Factory pins CR-1 single attempt and constructs no client."""

from __future__ import annotations

from codestrata.ai.provider_adapters.bedrock.factory import (
    BEDROCK_RETRY_POLICY,
    build_bedrock_executor,
    build_bedrock_provider,
)
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from tests.ai.provider_adapters.bedrock import fakes


def test_retry_policy_is_single_attempt_default() -> None:
    assert BEDROCK_RETRY_POLICY is DEFAULT_RETRY_POLICY
    assert BEDROCK_RETRY_POLICY.maximum_attempts == 1


def test_build_provider_does_not_call_injected_client() -> None:
    client = fakes.Client()
    build_bedrock_provider(client=client)
    assert client.calls == []


def test_executor_makes_exactly_one_converse_call() -> None:
    client = fakes.Client()
    executor = build_bedrock_executor(build_bedrock_provider(client=client))
    result = executor.execute(fakes.provider_request())
    assert result.attempts == 1
    assert result.retry_count == 0
    assert len(client.calls) == 1


def test_executor_does_not_retry_throttling_under_default_policy() -> None:
    client = fakes.Client(fakes.client_error("ThrottlingException"))
    delays: list[float] = []
    executor = build_bedrock_executor(
        build_bedrock_provider(client=client), sleeper=delays.append
    )
    result = executor.execute(fakes.provider_request())
    assert len(client.calls) == 1
    assert result.attempts == 1
    assert delays == []
