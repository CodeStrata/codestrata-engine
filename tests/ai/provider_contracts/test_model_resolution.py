"""Tests for resolve_provider_id / resolve_model_reference precedence.

These mirror the real, ground-truth precedence order documented on
``codestrata.ai.providers.factory.resolve_assess_model_id`` and
``codestrata.ai.providers.factory.create_assess_ai_provider`` — but every
test here calls the pure functions directly with injected values; none
reads ``os.environ`` or a file.
"""

from __future__ import annotations

import pytest

from codestrata.ai.provider_contracts.configuration_sources import SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId, ProviderModelReference
from codestrata.ai.provider_contracts.model_configuration import (
    resolve_model_reference,
    resolve_provider_id,
)


def test_resolve_provider_id_defaults_to_bedrock_when_unset() -> None:
    provider_id, source = resolve_provider_id(file_provider=None)
    assert provider_id is ProviderId.BEDROCK
    assert source is SourceCategory.DEFAULT


def test_resolve_provider_id_uses_configuration_file_value() -> None:
    provider_id, source = resolve_provider_id(file_provider="openai")
    assert provider_id is ProviderId.OPENAI
    assert source is SourceCategory.CONFIGURATION_FILE


def test_resolve_provider_id_normalizes_case_and_whitespace() -> None:
    provider_id, source = resolve_provider_id(file_provider="  OpenAI  ")
    assert provider_id is ProviderId.OPENAI
    assert source is SourceCategory.CONFIGURATION_FILE


def test_resolve_provider_id_rejects_unsupported_provider() -> None:
    with pytest.raises(ProviderContractValidationError):
        resolve_provider_id(file_provider="anthropic")


def test_resolve_model_reference_defaults_per_provider() -> None:
    ref, source = resolve_model_reference(
        provider_id=ProviderId.BEDROCK,
        cli_model_id=None,
        env_model_id=None,
        file_model_id=None,
    )
    assert isinstance(ref, ProviderModelReference)
    assert ref.value == "amazon.nova-lite-v1:0"
    assert source is SourceCategory.DEFAULT

    ref, source = resolve_model_reference(
        provider_id=ProviderId.OPENAI,
        cli_model_id=None,
        env_model_id=None,
        file_model_id=None,
    )
    assert ref.value == "gpt-4o-mini"
    assert source is SourceCategory.DEFAULT


def test_resolve_model_reference_cli_beats_env_beats_file_beats_default() -> None:
    ref, source = resolve_model_reference(
        provider_id=ProviderId.OPENAI,
        cli_model_id="cli-model",
        env_model_id="env-model",
        file_model_id="file-model",
    )
    assert (ref.value, source) == ("cli-model", SourceCategory.CLI)

    ref, source = resolve_model_reference(
        provider_id=ProviderId.OPENAI,
        cli_model_id=None,
        env_model_id="env-model",
        file_model_id="file-model",
    )
    assert (ref.value, source) == ("env-model", SourceCategory.ENVIRONMENT)

    ref, source = resolve_model_reference(
        provider_id=ProviderId.OPENAI,
        cli_model_id=None,
        env_model_id=None,
        file_model_id="file-model",
    )
    assert (ref.value, source) == ("file-model", SourceCategory.CONFIGURATION_FILE)


def test_resolve_model_reference_blank_candidates_are_skipped() -> None:
    ref, source = resolve_model_reference(
        provider_id=ProviderId.BEDROCK,
        cli_model_id="   ",
        env_model_id="",
        file_model_id="configured-model",
    )
    assert (ref.value, source) == ("configured-model", SourceCategory.CONFIGURATION_FILE)


def test_resolve_model_reference_rejects_non_provider_id() -> None:
    with pytest.raises(ProviderContractValidationError):
        resolve_model_reference(
            provider_id="bedrock",  # type: ignore[arg-type]
            cli_model_id=None,
            env_model_id=None,
            file_model_id=None,
        )


def test_resolve_functions_never_read_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    """Poisoning os.environ must not change resolution — these are pure functions."""

    monkeypatch.setenv("CODESTRATA_BEDROCK_MODEL_ID", "should-never-be-read")
    monkeypatch.setenv("CODESTRATA_OPENAI_MODEL_ID", "should-never-be-read")
    ref, source = resolve_model_reference(
        provider_id=ProviderId.BEDROCK,
        cli_model_id=None,
        env_model_id=None,
        file_model_id=None,
    )
    assert ref.value == "amazon.nova-lite-v1:0"
    assert source is SourceCategory.DEFAULT
