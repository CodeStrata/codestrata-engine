"""Privacy tests: configuration diagnostics/serialization never leak sensitive data."""

from __future__ import annotations

from codestrata.ai.provider_contracts.configuration_diagnostics import (
    diagnostic_view_of_configuration,
)
from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.configuration_serialization import (
    private_view_of_configuration,
    serialize_configuration_for_diagnostics,
    serialize_configuration_private,
)
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput

_FAKE_BASE_URL = "https://secret-proxy.internal.example/v1"
_FAKE_MODEL_ID = "org-internal-secret-model-name"


def _openai_configuration_with_secrets():
    input_data = LegacyConfigurationInput(
        provider="openai",
        cli_model_id=_FAKE_MODEL_ID,
        openai_api_key_env_name="OPENAI_API_KEY",
        openai_api_key_present=True,
        openai_base_url_configured=True,
    )
    return project_configuration(input_data)


def test_diagnostic_view_never_includes_raw_model_reference() -> None:
    configuration = _openai_configuration_with_secrets()
    view = diagnostic_view_of_configuration(configuration)
    assert view["model_reference"] == "[model_ref]"
    assert _FAKE_MODEL_ID not in repr(view)


def test_diagnostic_view_never_includes_base_url_value() -> None:
    configuration = _openai_configuration_with_secrets()
    view = diagnostic_view_of_configuration(configuration)
    assert "base_url" not in view["adapter"]
    assert view["adapter"]["base_url_configured"] is True


def test_serialized_diagnostic_form_excludes_model_and_base_url() -> None:
    configuration = _openai_configuration_with_secrets()
    text = serialize_configuration_for_diagnostics(configuration)
    assert _FAKE_MODEL_ID not in text
    assert '"base_url":' not in text
    assert '"base_url_configured":true' in text
    assert "/Users/" not in text
    assert "/home/" not in text


def test_private_view_includes_no_base_url_when_not_stored() -> None:
    """The privacy-preferred pipeline never even stores the raw base_url value."""

    configuration = _openai_configuration_with_secrets()
    private_view = private_view_of_configuration(configuration)
    assert private_view["adapter"]["base_url"] is None


def test_private_view_can_carry_a_raw_base_url_when_explicitly_constructed() -> None:
    from codestrata.ai.provider_contracts.adapter_configuration import (
        build_openai_adapter_configuration,
    )
    from codestrata.ai.provider_contracts.configuration_models import AIProviderConfiguration
    from codestrata.ai.provider_contracts.configuration_policy import CONTRACT_VERSION
    from codestrata.ai.provider_contracts.configuration_projection import UNWIRED_LIMITATIONS
    from codestrata.ai.provider_contracts.configuration_sources import (
        FieldSource,
        SourceCategory,
    )
    from codestrata.ai.provider_contracts.identifiers import (
        CapabilityId,
        ProviderId,
        ProviderModelReference,
    )
    from codestrata.ai.provider_contracts.requests import ExecutionOptions

    adapter = build_openai_adapter_configuration(
        api_key_env_name="OPENAI_API_KEY", api_key_present=True, base_url=_FAKE_BASE_URL
    )
    configuration = AIProviderConfiguration(
        configuration_version=CONTRACT_VERSION,
        provider_id=ProviderId.OPENAI,
        model_reference=ProviderModelReference("gpt-4o-mini"),
        capability_id=CapabilityId.MODERNIZATION_ADVISOR,
        execution_options=ExecutionOptions(),
        adapter_configuration=adapter,
        source_trace=(
            FieldSource("provider_id", SourceCategory.DEFAULT),
            FieldSource("model_reference", SourceCategory.DEFAULT),
        ),
        credential_requirements=(),
        limitations=UNWIRED_LIMITATIONS,
    )

    # The diagnostic (safe) view must still never include the raw URL...
    diagnostic_text = serialize_configuration_for_diagnostics(configuration)
    assert _FAKE_BASE_URL not in diagnostic_text

    # ...but the private (internal-only) view is explicitly allowed to.
    private_view = private_view_of_configuration(configuration)
    assert private_view["adapter"]["base_url"] == _FAKE_BASE_URL
    private_text = serialize_configuration_private(configuration)
    assert _FAKE_BASE_URL in private_text


def test_credential_requirements_never_carry_a_value_field() -> None:
    configuration = _openai_configuration_with_secrets()
    for requirement in configuration.credential_requirements:
        fields = {f.name for f in type(requirement).__dataclass_fields__.values()}
        assert "value" not in fields
        assert "secret" not in fields


def test_no_absolute_home_path_in_any_serialized_view() -> None:
    configuration = _openai_configuration_with_secrets()
    for text in (
        serialize_configuration_for_diagnostics(configuration),
        serialize_configuration_private(configuration),
    ):
        assert "/Users/" not in text
        assert "/home/" not in text
