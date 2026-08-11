"""The SV.11.6 fixtures stay synthetic: no network, no credentials, no waiting."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.ai.provider_contracts.requests import ResponseExpectation
from verification.openai_provider_migration import fixtures


class TestClientDouble:
    def test_the_client_records_every_call(self) -> None:
        client = fixtures.Client()

        client.chat.completions.create(model="m", messages=[])
        client.chat.completions.create(model="m", messages=[])

        assert len(client.calls) == 2
        assert client.calls[0]["model"] == "m"

    def test_the_client_returns_the_configured_response(self) -> None:
        configured = fixtures.response("payload")

        assert fixtures.Client(configured).chat.completions.create() is configured

    def test_the_client_raises_a_configured_exception_and_still_records_the_call(self) -> None:
        client = fixtures.Client(fixtures.sdk_exception("RateLimitError"))

        with pytest.raises(Exception, match="synthetic failure"):
            client.chat.completions.create(model="m")

        assert len(client.calls) == 1

    def test_the_client_exposes_only_the_chat_completions_surface(self) -> None:
        client = fixtures.Client()

        assert hasattr(client.chat, "completions")
        assert not hasattr(client, "embeddings")
        assert not hasattr(client, "responses")


class TestResponseBuilders:
    def test_the_default_response_carries_synthetic_content_and_usage(self) -> None:
        built = fixtures.response()

        assert built.choices[0].message.content == fixtures.SYNTHETIC_RESPONSE_TEXT
        assert built.usage.prompt_tokens == 11
        assert built.usage.total_tokens == 33

    def test_overrides_replace_top_level_attributes(self) -> None:
        built = fixtures.response("text", usage=None, id=None)

        assert built.usage is None
        assert built.id is None

    def test_a_synthetic_sdk_exception_carries_the_requested_class_name(self) -> None:
        error = fixtures.sdk_exception("AuthenticationError")

        assert type(error).__name__ == "AuthenticationError"
        assert isinstance(error, Exception)


class TestRequestBuilders:
    def test_the_provider_request_defaults_to_structured_json_advisor_input(self) -> None:
        request = fixtures.provider_request()

        assert request.capability is CapabilityId.MODERNIZATION_ADVISOR
        assert request.response_expectation is ResponseExpectation.STRUCTURED_JSON
        assert request.payload.instruction_text == fixtures.SYNTHETIC_INSTRUCTION

    def test_the_capability_and_expectation_are_overridable(self) -> None:
        request = fixtures.provider_request(
            response_expectation=ResponseExpectation.TEXT,
        )

        assert request.response_expectation is ResponseExpectation.TEXT

    def test_the_prompt_request_folds_system_developer_and_user_messages(self) -> None:
        roles = [message.role for message in fixtures.prompt_request().messages]

        assert roles == ["system", "developer", "user"]

    def test_prompt_request_parts_can_be_omitted(self) -> None:
        roles = [m.role for m in fixtures.prompt_request(developer=None, user=None).messages]

        assert roles == ["system"]

    def test_the_legacy_model_request_is_built_from_a_synthetic_context(self) -> None:
        request = fixtures.model_request()

        assert request.analysis_context.repository.name == "synthetic-repository"
        assert request.prompt_request.messages

    def test_the_invocation_options_default_to_the_pinned_answer_model(self) -> None:
        from verification.openai_provider_migration.contract import OPENAI_DEFAULT_ANSWER_MODEL

        assert fixtures.invocation_options().model_id == OPENAI_DEFAULT_ANSWER_MODEL


class TestIsolation:
    def test_the_no_environment_reader_reports_everything_unset(self) -> None:
        assert fixtures.no_environment("OPENAI_API_KEY") is None
        assert fixtures.no_environment("ANY_OTHER_NAME") is None

    def test_the_fixtures_module_never_touches_os_or_the_network(self) -> None:
        tree = ast.parse(Path(fixtures.__file__).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }

        assert not imported & {"os", "socket", "http", "requests", "httpx", "time", "openai"}

    def test_no_fixture_value_looks_like_a_real_credential(self) -> None:
        from verification.openai_provider_migration.reporting import (
            report_contains_forbidden_leak,
        )

        blob = Path(fixtures.__file__).read_text(encoding="utf-8")

        assert report_contains_forbidden_leak(blob) == []
