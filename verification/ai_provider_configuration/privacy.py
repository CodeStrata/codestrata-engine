"""Privacy characterization: configuration diagnostics/serialization never leak sensitive text."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.adapter_configuration import (
    build_openai_adapter_configuration,
)
from codestrata.ai.provider_contracts.configuration_diagnostics import (
    diagnostic_view_of_configuration,
)
from codestrata.ai.provider_contracts.configuration_models import AIProviderConfiguration
from codestrata.ai.provider_contracts.configuration_policy import CONTRACT_VERSION
from codestrata.ai.provider_contracts.configuration_projection import (
    UNWIRED_LIMITATIONS,
    project_configuration,
)
from codestrata.ai.provider_contracts.configuration_serialization import (
    private_view_of_configuration,
    serialize_configuration_for_diagnostics,
)
from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput
from codestrata.ai.provider_contracts.requests import ExecutionOptions
from verification.ai_provider_configuration.models import CheckResult

_FAKE_MODEL_ID = "fake-internal-secret-model-reference"
_FAKE_BASE_URL = "https://fake-secret-proxy.internal.example/v1"
_FAKE_ENV_NAME = "OPENAI_API_KEY"


def _configuration_with_fake_secrets() -> AIProviderConfiguration:
    return project_configuration(
        LegacyConfigurationInput(
            provider="openai",
            cli_model_id=_FAKE_MODEL_ID,
            openai_api_key_env_name=_FAKE_ENV_NAME,
            openai_api_key_present=True,
            openai_base_url_configured=True,
        )
    )


def _configuration_with_a_stored_raw_base_url() -> AIProviderConfiguration:
    adapter = build_openai_adapter_configuration(
        api_key_env_name=_FAKE_ENV_NAME, api_key_present=True, base_url=_FAKE_BASE_URL
    )
    return AIProviderConfiguration(
        configuration_version=CONTRACT_VERSION,
        provider_id=ProviderId.OPENAI,
        model_reference=ProviderModelReference(_FAKE_MODEL_ID),
        capability_id=CapabilityId.MODERNIZATION_ADVISOR,
        execution_options=ExecutionOptions(),
        adapter_configuration=adapter,
        source_trace=(
            FieldSource("provider_id", SourceCategory.DEFAULT),
            FieldSource("model_reference", SourceCategory.CLI),
        ),
        credential_requirements=(),
        limitations=UNWIRED_LIMITATIONS,
    )


def check_diagnostic_view_excludes_raw_model_reference() -> CheckResult:
    view = diagnostic_view_of_configuration(_configuration_with_fake_secrets())
    blob = repr(view)
    ok = _FAKE_MODEL_ID not in blob and view["model_reference"] == "[model_ref]"
    return CheckResult(
        name="configuration_diagnostic_view_excludes_raw_model_reference",
        category="privacy",
        ok=ok,
        detail="model_reference is redacted" if ok else "raw model reference leaked",
    )


def check_diagnostic_view_excludes_base_url_value() -> CheckResult:
    configuration = _configuration_with_a_stored_raw_base_url()
    view = diagnostic_view_of_configuration(configuration)
    blob = repr(view)
    ok = _FAKE_BASE_URL not in blob and "base_url" not in view["adapter"]
    return CheckResult(
        name="configuration_diagnostic_view_excludes_base_url_value",
        category="privacy",
        ok=ok,
        detail="base_url value absent from diagnostic view" if ok else "base_url leaked",
    )


def check_serialized_diagnostic_form_excludes_sensitive_text() -> CheckResult:
    configuration = _configuration_with_a_stored_raw_base_url()
    text = serialize_configuration_for_diagnostics(configuration)
    forbidden = (_FAKE_MODEL_ID, _FAKE_BASE_URL, "/Users/", "/home/")
    hits = [token for token in forbidden if token in text]
    ok = not hits
    return CheckResult(
        name="serialized_configuration_diagnostic_form_excludes_sensitive_text",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def check_private_view_is_a_distinct_superset_reserved_for_internal_use() -> CheckResult:
    """The private view MAY carry the raw base_url; the diagnostic view never does."""

    configuration = _configuration_with_a_stored_raw_base_url()
    private_view = private_view_of_configuration(configuration)
    diagnostic_view = diagnostic_view_of_configuration(configuration)
    ok = (
        private_view["adapter"].get("base_url") == _FAKE_BASE_URL
        and "base_url" not in diagnostic_view["adapter"]
    )
    return CheckResult(
        name="private_view_and_diagnostic_view_are_correctly_distinct",
        category="privacy",
        ok=ok,
        detail=(
            f"private_has_base_url={('base_url' in private_view['adapter'])} "
            f"diagnostic_has_base_url={('base_url' in diagnostic_view['adapter'])}"
        ),
    )


def check_env_var_name_is_permitted_but_never_a_value() -> CheckResult:
    """api_key_env_name (a variable *name*) is safe; there is no field for its value."""

    from codestrata.ai.provider_contracts.adapter_configuration import OpenAIAdapterConfiguration

    fields = {f.name for f in OpenAIAdapterConfiguration.__dataclass_fields__.values()}
    ok = "api_key_env_name" in fields and "api_key_value" not in fields and "api_key" not in fields
    return CheckResult(
        name="openai_adapter_configuration_carries_env_var_name_never_a_value",
        category="privacy",
        ok=ok,
        detail=f"fields={sorted(fields)}",
    )


def run_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_diagnostic_view_excludes_raw_model_reference(),
        check_diagnostic_view_excludes_base_url_value(),
        check_serialized_diagnostic_form_excludes_sensitive_text(),
        check_private_view_is_a_distinct_superset_reserved_for_internal_use(),
        check_env_var_name_is_permitted_but_never_a_value(),
    ]
    matrix = {
        "sample_diagnostic_view": diagnostic_view_of_configuration(
            _configuration_with_fake_secrets()
        )
    }
    return checks, matrix


__all__ = [
    "check_diagnostic_view_excludes_base_url_value",
    "check_diagnostic_view_excludes_raw_model_reference",
    "check_env_var_name_is_permitted_but_never_a_value",
    "check_private_view_is_a_distinct_superset_reserved_for_internal_use",
    "check_serialized_diagnostic_form_excludes_sensitive_text",
    "run_privacy_checks",
]
