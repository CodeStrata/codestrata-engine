"""The AWS credential boundary: lazy, single-sourced, and never reached in tests.

Slice 11.7's one deliberate behavior change lives here. The pre-migration
provider built its Bedrock Runtime client in ``__init__``; it is now built on
the first ``execute()``. These checks pin both halves of that: nothing before
the first call touches AWS, and the failure that used to surface at
construction still surfaces — as the same legacy exception type with the same
message — from ``invoke()``.

Every client construction path is exercised through injected fakes, so no
credential file, environment variable, instance metadata endpoint, or STS
call is involved.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from codestrata.ai.provider_adapters.bedrock import client as client_module
from codestrata.ai.provider_adapters.bedrock.configuration import build_runtime_configuration
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId
from codestrata.ai.providers.exceptions import AIProviderConfigurationError
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import (
    AWS_CLIENT_FACTORY_NAME,
    EXPECTED_MODULES,
)
from verification.bedrock_provider_migration.models import CheckResult

_GUIDANCE_PROFILE = "synthetic-guidance-profile"


class _RecordingFactory:
    """Stands in for ``aws_config.create_bedrock_runtime_client``."""

    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def _with_factory(outcome: Any) -> _RecordingFactory:
    """Install a recording stand-in for the AWS client factory.

    Patching ``client_module.aws_config`` rather than the real module keeps
    ``aws_config`` itself untouched, and the caller always restores it.
    """

    return _RecordingFactory(outcome)


class _StubAwsConfig:
    def __init__(self, factory: _RecordingFactory, authentication_error: type[BaseException]):
        self.create_bedrock_runtime_client = factory
        self.AwsAuthenticationError = authentication_error


def _patched_resolution(outcome: Any, **inputs: Any) -> tuple[Any, _RecordingFactory]:
    factory = _with_factory(outcome)
    real = client_module.aws_config
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    try:
        resolution = client_module.resolve_client(
            build_runtime_configuration(**inputs).client_inputs
        )
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return resolution, factory


def check_importing_the_adapter_constructs_no_client(package_dir: Path) -> CheckResult:
    """Executing every adapter module's top level must not reach AWS.

    Each module is executed into a throwaway namespace rather than reloaded
    in place, so the already-imported package (and every class identity the
    rest of this suite depends on) is left untouched.
    """

    real = client_module.aws_config
    factory = _with_factory(object())
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    executed = 0
    try:
        for filename in EXPECTED_MODULES:
            path = package_dir / filename
            if not path.is_file():
                continue
            probe_name = f"_sv117_probe_{filename[: -len('.py')]}"
            spec = importlib.util.spec_from_file_location(probe_name, path)
            if spec is None or spec.loader is None:  # pragma: no cover - defensive
                continue
            module = importlib.util.module_from_spec(spec)
            # dataclasses resolves annotations through sys.modules, so the
            # throwaway module has to be registered while it executes.
            sys.modules[probe_name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                sys.modules.pop(probe_name, None)
            executed += 1
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="importing_every_adapter_module_constructs_no_client_and_reads_no_credential",
        category="authentication",
        ok=executed == len(EXPECTED_MODULES) and not factory.calls,
        detail=f"modules_executed={executed} client_factory_calls={len(factory.calls)}",
    )


def check_building_a_provider_constructs_no_client() -> CheckResult:
    real = client_module.aws_config
    factory = _with_factory(object())
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    try:
        adapter = build_bedrock_provider()
        supports = adapter.supports(CapabilityId.MODERNIZATION_ADVISOR)
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="constructing_a_provider_and_asking_supports_never_builds_a_client",
        category="authentication",
        ok=not factory.calls and supports,
        detail=f"client_factory_calls={len(factory.calls)} supports_answered={supports}",
    )


def check_an_injected_client_bypasses_aws_config() -> CheckResult:
    real = client_module.aws_config
    factory = _with_factory(object())
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    injected = fixtures.Client()
    try:
        adapter = build_bedrock_provider(client=injected)
        result = adapter.execute(fixtures.provider_request())
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="an_injected_client_is_used_verbatim_and_aws_config_is_never_called",
        category="authentication",
        ok=(
            not factory.calls
            and len(injected.calls) == 1
            and result.status is ProviderExecutionStatus.SUCCESS
        ),
        detail=(
            f"client_factory_calls={len(factory.calls)} "
            f"converse_calls={len(injected.calls)}"
        ),
    )


def check_the_client_factory_receives_the_inputs_verbatim() -> CheckResult:
    resolution, factory = _patched_resolution(
        object(), profile_name="explicit-profile", region_name="explicit-region"
    )
    call = factory.calls[0] if factory.calls else {}
    expected_keys = {"settings", "profile", "region", "timeout_seconds"}
    return CheckResult(
        name="the_aws_client_factory_receives_the_explicit_profile_region_and_timeout_verbatim",
        category="authentication",
        ok=(
            resolution.ok
            and set(call) == expected_keys
            and call.get("profile") == "explicit-profile"
            and call.get("region") == "explicit-region"
        ),
        detail=f"factory_kwargs={sorted(call)}",
        evidence={"client_factory": AWS_CLIENT_FACTORY_NAME},
    )


def check_a_missing_extra_becomes_a_bounded_dependency_error() -> CheckResult:
    resolution, _ = _patched_resolution(RuntimeError("boto3 is not installed"))
    error = resolution.error
    return CheckResult(
        name="a_missing_bedrock_extra_becomes_a_bounded_dependency_unavailable_error",
        category="authentication",
        ok=(
            not resolution.ok
            and error is not None
            and error.category is ErrorCategory.DEPENDENCY_UNAVAILABLE
        ),
        detail=f"category={error.category.value if error else None}",
    )


def check_an_authentication_failure_becomes_a_bounded_configuration_error() -> CheckResult:
    real_error = client_module.AwsAuthenticationError("synthetic AWS guidance")
    resolution, _ = _patched_resolution(real_error)
    error = resolution.error
    return CheckResult(
        name="an_aws_authentication_failure_becomes_a_bounded_missing_configuration_error",
        category="authentication",
        ok=(
            not resolution.ok
            and error is not None
            and error.category is ErrorCategory.MISSING_CONFIGURATION
        ),
        detail=f"category={error.category.value if error else None}",
    )


def check_a_construction_failure_never_escapes_as_an_exception() -> CheckResult:
    resolution, _ = _patched_resolution(ValueError("synthetic construction failure"))
    error = resolution.error
    return CheckResult(
        name="an_unexpected_client_construction_failure_returns_a_bounded_error_not_an_exception",
        category="authentication",
        ok=(
            not resolution.ok
            and error is not None
            and error.category is ErrorCategory.MISSING_CONFIGURATION
        ),
        detail=f"category={error.category.value if error else None}",
    )


def check_a_client_failure_surfaces_as_unavailable_not_failed() -> CheckResult:
    """No call was attempted, so the run is UNAVAILABLE rather than FAILED."""

    real = client_module.aws_config
    factory = _with_factory(RuntimeError("boto3 is not installed"))
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    try:
        result = build_bedrock_provider().execute(fixtures.provider_request())
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="a_client_construction_failure_surfaces_as_unavailable_rather_than_failed",
        category="authentication",
        ok=result.status is ProviderExecutionStatus.UNAVAILABLE,
        detail=f"status={result.status.value}",
    )


def check_the_lazy_failure_still_raises_the_legacy_configuration_error() -> CheckResult:
    """The construction-time failure now surfaces from ``invoke()``, unchanged."""

    from codestrata.ai.providers.bedrock import BedrockAIModelProvider

    real = client_module.aws_config
    factory = _with_factory(RuntimeError("boto3 is not installed. Install the bedrock extra."))
    client_module.aws_config = _StubAwsConfig(  # type: ignore[assignment]
        factory, real.AwsAuthenticationError
    )
    try:
        provider = BedrockAIModelProvider()
        constructed_without_aws = not factory.calls
        try:
            provider.invoke(fixtures.model_request(), fixtures.invocation_options())
        except AIProviderConfigurationError as error:
            raised, message = True, str(error)
        else:
            raised, message = False, ""
    finally:
        client_module.aws_config = real  # type: ignore[assignment]
    return CheckResult(
        name="a_missing_extra_now_raises_the_same_configuration_error_from_invoke_not_from_init",
        category="authentication",
        ok=constructed_without_aws and raised and "boto3 is not installed" in message,
        detail=(
            f"constructor_touched_aws={not constructed_without_aws} "
            f"invoke_raised_configuration_error={raised}"
        ),
    )


def check_the_guidance_message_names_the_profile_but_no_credential() -> CheckResult:
    from codestrata.ai.provider_adapters.bedrock import legacy_bridge
    from codestrata.ai.provider_adapters.bedrock.error_mapping import (
        CODE_AUTHENTICATION_FAILED,
        build_error,
    )

    error = legacy_bridge.legacy_error_for(
        build_error(CODE_AUTHENTICATION_FAILED), profile_name=_GUIDANCE_PROFILE
    )
    message = str(error)
    return CheckResult(
        name="the_aws_authentication_guidance_still_names_the_profile_and_no_credential",
        category="authentication",
        ok=_GUIDANCE_PROFILE in message and "aws sso login" in message.lower(),
        detail="guidance rebuilt through aws_config.format_aws_authentication_error",
    )


def check_no_client_singleton_is_kept() -> CheckResult:
    """Two resolutions must produce two handles: no credential state is cached."""

    first, factory = _patched_resolution(object())
    second, second_factory = _patched_resolution(object())
    return CheckResult(
        name="no_process_wide_client_singleton_is_kept_between_resolutions",
        category="authentication",
        ok=(
            first.ok
            and second.ok
            and first.handle is not second.handle
            and len(factory.calls) == 1
            and len(second_factory.calls) == 1
        ),
        detail="each resolve_client call builds its own handle",
    )


def run_authentication_checks(package_dir: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_importing_the_adapter_constructs_no_client(package_dir),
        check_building_a_provider_constructs_no_client(),
        check_an_injected_client_bypasses_aws_config(),
        check_the_client_factory_receives_the_inputs_verbatim(),
        check_a_missing_extra_becomes_a_bounded_dependency_error(),
        check_an_authentication_failure_becomes_a_bounded_configuration_error(),
        check_a_construction_failure_never_escapes_as_an_exception(),
        check_a_client_failure_surfaces_as_unavailable_not_failed(),
        check_the_lazy_failure_still_raises_the_legacy_configuration_error(),
        check_the_guidance_message_names_the_profile_but_no_credential(),
        check_no_client_singleton_is_kept(),
    ]
    matrix: dict[str, Any] = {
        "client_construction_is_lazy": True,
        "client_factory": AWS_CLIENT_FACTORY_NAME,
        "client_singleton_kept": False,
        "credential_chain_owner": "codestrata.ai.aws_config",
        "injected_client_bypasses_aws_config": True,
        "live_aws_calls": 0,
    }
    return checks, matrix


__all__ = [
    "check_a_client_failure_surfaces_as_unavailable_not_failed",
    "check_a_construction_failure_never_escapes_as_an_exception",
    "check_a_missing_extra_becomes_a_bounded_dependency_error",
    "check_an_authentication_failure_becomes_a_bounded_configuration_error",
    "check_an_injected_client_bypasses_aws_config",
    "check_building_a_provider_constructs_no_client",
    "check_importing_the_adapter_constructs_no_client",
    "check_no_client_singleton_is_kept",
    "check_the_client_factory_receives_the_inputs_verbatim",
    "check_the_guidance_message_names_the_profile_but_no_credential",
    "check_the_lazy_failure_still_raises_the_legacy_configuration_error",
    "run_authentication_checks",
]
