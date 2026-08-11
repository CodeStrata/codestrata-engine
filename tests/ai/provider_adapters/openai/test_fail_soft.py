"""Fail-soft: the assess layer still derives the same AI status from our messages.

``application.assessment.service._map_provider_error`` classifies a provider
failure by inspecting the *message text* of the raised legacy exception. That
makes the migrated wrapper's messages load-bearing: reword one and a run that
used to report ``authentication_failed`` starts reporting
``provider_failed``. These tests pin the observable end of that chain.
"""

from __future__ import annotations

import pytest

from codestrata.ai.prompts import ModernizationPromptBuilder
from codestrata.ai.providers.models import (
    ModelInvocationOptions,
    ModernizationModelRequest,
)
from codestrata.ai.providers.openai_provider import OpenAIAIModelProvider
from codestrata.ai.providers.parsing import sanitize_provider_text
from codestrata.application.assessment.service import _map_provider_error
from codestrata.reporting.modernization_models import AIExecutionStatus
from tests.ai.provider_adapters.openai import fakes
from tests.ai.test_ai_model_providers import _context


def _invoke_expecting_failure(outcome: object) -> Exception:
    context = _context("SEC001")
    request = ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )
    provider = OpenAIAIModelProvider(client=fakes.FakeClient(outcome))
    with pytest.raises(Exception) as caught:  # noqa: PT011 - type asserted by caller
        provider.invoke(request, ModelInvocationOptions(model_id="gpt-4o-mini"))
    return caught.value


@pytest.mark.parametrize("exception_name", ["AuthenticationError", "PermissionDeniedError"])
def test_auth_failures_still_map_to_authentication_failed(exception_name: str) -> None:
    error = _invoke_expecting_failure(fakes.named_exception(exception_name))

    mapped = _map_provider_error(error, model_id="gpt-4o-mini")

    assert mapped.ai_status is AIExecutionStatus.AUTHENTICATION_FAILED


@pytest.mark.parametrize(
    "exception_name",
    ["APITimeoutError", "RateLimitError", "APIConnectionError", "InternalServerError"],
)
def test_transient_failures_still_map_to_provider_failed(exception_name: str) -> None:
    error = _invoke_expecting_failure(fakes.named_exception(exception_name))

    mapped = _map_provider_error(error, model_id="gpt-4o-mini")

    assert mapped.ai_status is AIExecutionStatus.PROVIDER_FAILED


@pytest.mark.parametrize("exception_name", ["BadRequestError", "NotFoundError"])
def test_invalid_request_failures_still_map_to_provider_failed(exception_name: str) -> None:
    error = _invoke_expecting_failure(fakes.named_exception(exception_name))

    mapped = _map_provider_error(error, model_id="gpt-4o-mini")

    assert mapped.ai_status is AIExecutionStatus.PROVIDER_FAILED


def test_missing_api_key_still_maps_to_provider_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from codestrata.config.settings import OpenAISettings

    monkeypatch.delenv("MY_KEY_VAR", raising=False)
    context = _context("SEC001")
    request = ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )
    provider = OpenAIAIModelProvider(openai_settings=OpenAISettings(api_key_env="MY_KEY_VAR"))

    with pytest.raises(Exception) as caught:  # noqa: PT011 - message asserted below
        provider.invoke(request, ModelInvocationOptions(model_id="gpt-4o-mini"))

    mapped = _map_provider_error(caught.value, model_id="gpt-4o-mini")
    assert mapped.ai_status is AIExecutionStatus.PROVIDER_FAILED


def test_sdk_text_passes_through_the_same_sanitizer_as_before() -> None:
    """The legacy message embeds ``sanitize_provider_text(str(exc))``, unchanged.

    That sanitizer redacts secrets and bounds the length; it deliberately does
    not strip paths, and the migration must not change either behavior.
    """

    raw = "rejected key sk-abcdefghijklmnopqrstuvwxyz0123456789 " + "x" * 5000
    error = _invoke_expecting_failure(fakes.named_exception("BadRequestError", raw))

    message = str(error)

    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in message
    assert message == (
        "OpenAI invalid model or request configuration: " + sanitize_provider_text(raw)
    )


def test_enrichment_service_makes_exactly_one_provider_call() -> None:
    """CR-1: one ``invoke()`` per assess run, and one wire call inside it."""

    client = fakes.FakeClient(fakes.named_exception("RateLimitError"))
    context = _context("SEC001")
    request = ModernizationModelRequest(
        prompt_request=ModernizationPromptBuilder().build(context),
        analysis_context=context,
    )

    with pytest.raises(Exception):  # noqa: PT011, B017 - counting calls, not asserting type
        OpenAIAIModelProvider(client=client).invoke(
            request, ModelInvocationOptions(model_id="gpt-4o-mini")
        )

    assert len(client.calls) == 1
