"""Credential handling: lazy construction, one boundary, no leaks, no live calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codestrata.ai.provider_adapters.openai import client as client_module
from codestrata.ai.provider_adapters.openai import error_mapping
from codestrata.ai.provider_adapters.openai.configuration import (
    OpenAIClientInputs,
    build_runtime_configuration,
)
from codestrata.ai.provider_adapters.openai.factory import build_openai_provider
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.config.settings import OpenAISettings
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.contract import CREDENTIAL_BOUNDARY_MODULE
from verification.openai_provider_migration.models import CheckResult

_SECRET_ENV_NAME = "SYNTHETIC_OPENAI_KEY_VAR"
_SYNTHETIC_BASE_URL = "https://synthetic-gateway.invalid/v1"


class _RecordingReader:
    """An environment reader that records every name it is asked for."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.names.append(name)
        return None


def _client_inputs(*, base_url: str | None = None) -> OpenAIClientInputs:
    settings = OpenAISettings(api_key_env=_SECRET_ENV_NAME, base_url=base_url)
    return build_runtime_configuration(openai_settings=settings).client_inputs


def check_client_construction_is_lazy() -> CheckResult:
    """Building the adapter constructs no client and reads no environment."""

    reader = _RecordingReader()
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SECRET_ENV_NAME),
        environment_reader=reader,
    )
    return CheckResult(
        name="building_the_adapter_constructs_no_client_and_reads_no_environment",
        category="authentication",
        ok=adapter.client_injected is False and not reader.names,
        detail=f"environment_reads_during_construction={len(reader.names)}",
    )


def check_supports_does_not_read_credentials() -> CheckResult:
    """Capability discovery must be answerable with AI disabled and no key set."""

    reader = _RecordingReader()
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SECRET_ENV_NAME),
        environment_reader=reader,
    )
    answers = [adapter.supports(capability) for capability in CapabilityId]
    return CheckResult(
        name="capability_discovery_never_reads_credentials",
        category="authentication",
        ok=not reader.names and any(answers),
        detail=f"environment_reads_during_supports={len(reader.names)}",
    )


def check_missing_api_key_is_a_bounded_unavailable_result() -> CheckResult:
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SECRET_ENV_NAME),
        environment_reader=fixtures.no_environment,
    )
    result = adapter.execute(fixtures.provider_request())
    error = result.error
    ok = (
        result.status is ProviderExecutionStatus.UNAVAILABLE
        and error is not None
        and error.category is ErrorCategory.MISSING_CONFIGURATION
        and error.code == error_mapping.CODE_MISSING_API_KEY
    )
    return CheckResult(
        name="a_missing_api_key_yields_unavailable_with_missing_configuration",
        category="authentication",
        ok=ok,
        detail=f"status={result.status.value} code={error.code if error else None}",
    )


def check_missing_api_key_does_not_raise() -> CheckResult:
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SECRET_ENV_NAME),
        environment_reader=fixtures.no_environment,
    )
    raised: str | None = None
    try:
        adapter.execute(fixtures.provider_request())
    except Exception as error:  # noqa: BLE001 - verification asserts non-raising
        raised = type(error).__name__
    return CheckResult(
        name="a_missing_api_key_is_returned_rather_than_raised",
        category="authentication",
        ok=raised is None,
        detail=f"raised={raised}",
    )


def check_an_injected_client_bypasses_the_environment_entirely() -> CheckResult:
    reader = _RecordingReader()
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SECRET_ENV_NAME),
        client=fixtures.Client(fixtures.response()),
        environment_reader=reader,
    )
    result = adapter.execute(fixtures.provider_request())
    ok = not reader.names and result.status is ProviderExecutionStatus.SUCCESS
    return CheckResult(
        name="an_injected_client_bypasses_the_credential_boundary_entirely",
        category="authentication",
        ok=ok,
        detail=f"environment_reads={len(reader.names)} status={result.status.value}",
    )


def check_the_client_handle_repr_is_redacted() -> CheckResult:
    resolution = client_module.resolve_client(
        _client_inputs(base_url=_SYNTHETIC_BASE_URL),
        injected_client=fixtures.Client(fixtures.response()),
    )
    handle = resolution.handle
    rendered = repr(handle)
    ok = (
        handle is not None
        and handle.injected is True
        and handle.base_url_configured is True
        and "synthetic-gateway" not in rendered
        and _SECRET_ENV_NAME in rendered
    )
    return CheckResult(
        name="client_handle_repr_reports_the_env_var_name_but_no_base_url_or_secret",
        category="authentication",
        ok=ok,
        detail="OpenAIClientHandle.__repr__ renders presence booleans only",
    )


def check_a_missing_optional_extra_is_bounded() -> CheckResult:
    """A missing ``openai`` extra is a bounded dependency error, not a crash."""

    error = error_mapping.build_error(error_mapping.CODE_MISSING_DEPENDENCY)
    importable = client_module.openai_extra_importable()
    ok = error.category is ErrorCategory.DEPENDENCY_UNAVAILABLE and isinstance(importable, bool)
    return CheckResult(
        name="a_missing_openai_extra_maps_to_a_bounded_dependency_unavailable_error",
        category="authentication",
        ok=ok,
        detail=f"category={error.category.value} extra_importable={importable}",
    )


def check_there_is_no_client_singleton() -> CheckResult:
    """No module-level client is cached, so two adapters never share client state."""

    first = build_openai_provider(client=fixtures.Client(fixtures.response()))
    second = build_openai_provider(client=fixtures.Client(fixtures.response()))
    cached = sorted(
        name
        for name, value in vars(client_module).items()
        if name.lower().endswith("client") and not callable(value) and not isinstance(value, type)
    )
    return CheckResult(
        name="no_module_level_client_singleton_is_cached",
        category="authentication",
        ok=first is not second and not cached,
        detail=f"module_level_client_globals={cached}",
    )


def check_verification_never_uses_the_real_environment_reader() -> CheckResult:
    """Every execution in this suite injects a client or a stub reader."""

    package = Path(__file__).parent
    allowed = {"authentication.py", "dependency_boundary.py", "privacy.py"}
    offenders = sorted(
        path.name
        for path in package.glob("*.py")
        if path.name not in allowed
        and "default_environment_reader" in path.read_text(encoding="utf-8")
    )
    return CheckResult(
        name="verification_never_executes_through_the_real_environment_reader",
        category="authentication",
        ok=not offenders,
        detail=f"modules_referencing_the_real_reader={offenders}",
    )


def run_authentication_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_client_construction_is_lazy(),
        check_supports_does_not_read_credentials(),
        check_missing_api_key_is_a_bounded_unavailable_result(),
        check_missing_api_key_does_not_raise(),
        check_an_injected_client_bypasses_the_environment_entirely(),
        check_the_client_handle_repr_is_redacted(),
        check_a_missing_optional_extra_is_bounded(),
        check_there_is_no_client_singleton(),
        check_verification_never_uses_the_real_environment_reader(),
    ]
    matrix: dict[str, Any] = {
        "credential_boundary_module": CREDENTIAL_BOUNDARY_MODULE,
        "missing_api_key_category": ErrorCategory.MISSING_CONFIGURATION.value,
        "missing_api_key_status": ProviderExecutionStatus.UNAVAILABLE.value,
        "missing_dependency_category": ErrorCategory.DEPENDENCY_UNAVAILABLE.value,
    }
    return checks, matrix


__all__ = [
    "check_a_missing_optional_extra_is_bounded",
    "check_an_injected_client_bypasses_the_environment_entirely",
    "check_client_construction_is_lazy",
    "check_missing_api_key_does_not_raise",
    "check_missing_api_key_is_a_bounded_unavailable_result",
    "check_supports_does_not_read_credentials",
    "check_the_client_handle_repr_is_redacted",
    "check_there_is_no_client_singleton",
    "check_verification_never_uses_the_real_environment_reader",
    "run_authentication_checks",
]
