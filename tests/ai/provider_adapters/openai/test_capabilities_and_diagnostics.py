"""Capabilities come from the Slice 11.5 catalog; diagnostics stay redacted."""

from __future__ import annotations

import json

from codestrata.ai.provider_adapters.openai import capabilities, diagnostics, error_mapping
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.capability_catalogs import OPENAI_CAPABILITY_PROFILE
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.config.settings import OpenAISettings
from tests.ai.provider_adapters.openai import fakes


def test_capabilities_are_read_from_the_shared_catalog() -> None:
    assert capabilities.OPENAI_PROVIDER_ID is ProviderId.OPENAI
    assert capabilities.openai_capability_profile() is OPENAI_CAPABILITY_PROFILE
    assert capabilities.SUPPORTED_CAPABILITY_IDS == frozenset(
        OPENAI_CAPABILITY_PROFILE.supported_capability_ids
    )


def test_native_structured_json_is_declared() -> None:
    assert capabilities.SUPPORTS_NATIVE_STRUCTURED_JSON is True


def test_declares_capability_rejects_non_capability_values() -> None:
    assert capabilities.declares_capability(CapabilityId.MODERNIZATION_ADVISOR) is True
    assert capabilities.declares_capability("modernization_advisor") is False  # type: ignore[arg-type]
    assert capabilities.declares_capability(None) is False  # type: ignore[arg-type]


def test_adapter_supports_exactly_what_the_catalog_declares() -> None:
    adapter = build_openai_provider()

    for capability in CapabilityId:
        expected = capability in OPENAI_CAPABILITY_PROFILE.supported_capability_ids
        assert adapter.supports(capability) is expected


def test_adapter_diagnostic_view_is_redacted() -> None:
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(
            api_key_env="MY_KEY_VAR", base_url="https://private-gateway.example/v1"
        ),
        client=fakes.FakeClient(),
    )

    view = diagnostics.diagnostic_view_of_adapter(adapter)
    serialized = json.dumps(view, sort_keys=True)

    assert view["api_key_env_name"] == "MY_KEY_VAR"
    assert view["base_url_configured"] is True
    assert view["client_injected"] is True
    assert view["provider_id"] == "openai"
    assert "private-gateway" not in serialized
    assert "sk-" not in serialized


def test_adapter_diagnostic_view_reports_the_adapter_limitations() -> None:
    view = diagnostics.diagnostic_view_of_adapter(build_openai_provider())

    assert view["adapter_limitations"] == ["bedrock_remains_legacy", "single_attempt_by_default"]


def test_capability_diagnostic_view_is_json_serializable() -> None:
    view = diagnostics.diagnostic_view_of_capabilities()

    assert json.dumps(view, sort_keys=True)


def test_result_diagnostic_view_carries_no_response_text() -> None:
    adapter = build_openai_provider(
        client=fakes.FakeClient(fakes.json_response({"secret": "response text"}))
    )
    result = adapter.execute(fakes.provider_request())

    view = diagnostics.diagnostic_view_of_provider_result(result)

    assert "response text" not in json.dumps(view, sort_keys=True)


def test_execution_diagnostic_view_carries_no_response_text_or_request_id() -> None:
    adapter = build_openai_provider(
        client=fakes.FakeClient(
            fakes.json_response({"secret": "response text"}, id="chatcmpl-secret")
        )
    )
    execution = build_openai_executor(adapter).execute(fakes.provider_request())

    serialized = json.dumps(diagnostics.diagnostic_view_of_execution(execution), sort_keys=True)

    assert "response text" not in serialized
    assert "chatcmpl-secret" not in serialized


def test_error_category_matrix_covers_every_code() -> None:
    matrix = diagnostics.error_category_matrix()

    assert set(matrix) == set(error_mapping.CATEGORY_BY_CODE)
    assert matrix[error_mapping.CODE_TIMEOUT] == "timeout"


def test_retryability_matrix_matches_the_default_partition() -> None:
    matrix = diagnostics.retryability_matrix()

    assert matrix[error_mapping.CODE_TIMEOUT] is True
    assert matrix[error_mapping.CODE_RATE_LIMITED] is True
    assert matrix[error_mapping.CODE_PROVIDER_UNAVAILABLE] is True
    assert matrix[error_mapping.CODE_AUTHENTICATION_FAILED] is False
    assert matrix[error_mapping.CODE_INVALID_MODEL] is False
    assert matrix[error_mapping.CODE_EMPTY_RESPONSE] is False


def test_diagnostics_never_accept_the_bridge_only_invocation_detail() -> None:
    exported = {name for name in dir(diagnostics) if name.startswith("diagnostic_view_")}

    assert "diagnostic_view_of_invocation_detail" not in exported
