"""Factory: pinned policies, settings precedence, and no import-time client."""

from __future__ import annotations

import pytest

from codestrata.ai.provider_adapters.openai import factory
from codestrata.ai.provider_adapters.openai.adapter import OpenAIProvider
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.executor import AIProviderExecutor
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.provider_contracts.timeout_policy import DEFAULT_TIMEOUT_POLICY
from codestrata.config.settings import CodestrataSettings, OpenAISettings
from tests.ai.provider_adapters.openai import fakes


def test_pinned_policies_preserve_the_single_attempt_envelope() -> None:
    assert factory.OPENAI_RETRY_POLICY is DEFAULT_RETRY_POLICY
    assert factory.OPENAI_RETRY_POLICY.maximum_attempts == 1
    assert factory.OPENAI_TIMEOUT_POLICY is DEFAULT_TIMEOUT_POLICY
    assert factory.OPENAI_TIMEOUT_POLICY.timeout_seconds == 60.0


def test_build_provider_returns_an_adapter_without_a_client() -> None:
    adapter = factory.build_openai_provider()

    assert isinstance(adapter, OpenAIProvider)
    assert adapter.client_injected is False


def test_build_provider_reads_no_environment_and_constructs_no_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.ai.provider_adapters.openai import client as client_module

    monkeypatch.setattr(
        client_module,
        "resolve_client",
        lambda *_a, **_k: pytest.fail("no client may be constructed by the factory"),
    )
    monkeypatch.setattr(
        client_module,
        "default_environment_reader",
        lambda _name: pytest.fail("no environment read may happen in the factory"),
    )

    factory.build_openai_provider(openai_settings=OpenAISettings())
    factory.build_openai_executor(factory.build_openai_provider())


def test_explicit_openai_settings_win_over_the_settings_tree() -> None:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {"provider": "openai", "openai": {"api_key_env": "FROM_TREE"}},
        }
    )

    resolved = factory.resolve_openai_settings(
        settings=settings, openai_settings=OpenAISettings(api_key_env="EXPLICIT")
    )

    assert resolved.api_key_env == "EXPLICIT"


def test_settings_tree_is_used_when_no_block_is_passed() -> None:
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {"provider": "openai", "openai": {"api_key_env": "FROM_TREE"}},
        }
    )

    assert factory.resolve_openai_settings(settings=settings).api_key_env == "FROM_TREE"


def test_defaults_are_used_when_nothing_is_passed() -> None:
    assert factory.resolve_openai_settings().api_key_env == "OPENAI_API_KEY"


def test_executor_wraps_the_adapter_and_runs_one_attempt() -> None:
    client = fakes.FakeClient(fakes.json_response({"a": 1}))
    adapter = factory.build_openai_provider(client=client)

    executor = factory.build_openai_executor(adapter)
    execution = executor.execute(fakes.provider_request())

    assert isinstance(executor, AIProviderExecutor)
    assert execution.status is ProviderExecutionStatus.SUCCESS
    assert len(client.calls) == 1
    assert execution.attempts == 1
    assert execution.retry_count == 0


def test_a_retryable_failure_still_makes_only_one_call() -> None:
    client = fakes.FakeClient(fakes.named_exception("RateLimitError"))
    adapter = factory.build_openai_provider(client=client)

    execution = factory.build_openai_executor(adapter).execute(fakes.provider_request())

    assert execution.status is ProviderExecutionStatus.FAILED
    assert execution.attempts == 1
    assert execution.retry_count == 0
    assert len(client.calls) == 1


def test_the_default_sleeper_never_sleeps() -> None:
    """A no-op default guarantees no wall-clock wait even under a multi-attempt policy."""

    assert factory._no_sleep(30.0) is None


def test_executor_limitation_labels_predate_the_migration() -> None:
    """SV.11.4's labels are deliberately frozen so prior-slice verdicts stay stable.

    ``executor_not_wired`` and ``providers_not_migrated`` are no longer
    literally true for OpenAI; ``engine/docs/ai-provider-openai.md`` records
    that, and SV.11.6 reports it as a known limitation rather than editing the
    Slice 11.4 constant.
    """

    from codestrata.ai.provider_contracts.executor import EXECUTOR_LIMITATIONS

    client = fakes.FakeClient(fakes.json_response({"a": 1}))
    execution = factory.build_openai_executor(
        factory.build_openai_provider(client=client)
    ).execute(fakes.provider_request())

    assert execution.limitations == EXECUTOR_LIMITATIONS
    assert "executor_not_wired" in execution.limitations


def test_a_supplied_configuration_short_circuits_settings_resolution() -> None:
    runtime = fakes.runtime_configuration(
        openai_settings=OpenAISettings(api_key_env="PRE_BUILT"), timeout_seconds=12.0
    )

    adapter = factory.build_openai_provider(configuration=runtime)

    assert adapter.configuration is runtime
    assert adapter.configuration.api_key_env_name == "PRE_BUILT"
