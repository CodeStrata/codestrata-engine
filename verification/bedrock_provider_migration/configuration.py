"""Configuration: same keys, same defaults, same precedence, redacted views."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock.configuration import (
    AWS_PROFILE_ENV_NAME,
    AWS_REGION_ENV_NAMES,
    build_runtime_configuration,
    resolve_configured_profile_name,
    resolve_configured_region_name,
    resolve_max_retries,
)
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.config.settings import CodestrataSettings
from verification.bedrock_provider_migration.contract import (
    AWS_CONFIG_KEYS,
    AWS_PROFILE_ENV_NAME as EXPECTED_PROFILE_ENV_NAME,
    AWS_REGION_ENV_NAMES as EXPECTED_REGION_ENV_NAMES,
    EXPECTED_TIMEOUT_SECONDS,
)
from verification.bedrock_provider_migration.determinism import canonical_json
from verification.bedrock_provider_migration.models import CheckResult

_PROFILE_VALUE = "synthetic-configuration-profile"
_REGION_VALUE = "synthetic-configuration-region"


def settings_with(
    *,
    profile: str | None = None,
    region: str | None = None,
    bedrock_region: str | None = None,
    max_retries: int | None = None,
) -> CodestrataSettings:
    payload: dict[str, Any] = {"repository": {"path": "."}, "aws": {}, "ai": {"bedrock": {}}}
    if profile is not None:
        payload["aws"]["profile"] = profile
    if region is not None:
        payload["aws"]["region"] = region
    if bedrock_region is not None:
        payload["ai"]["bedrock"]["region"] = bedrock_region
    if max_retries is not None:
        payload["ai"]["bedrock"]["max_retries"] = max_retries
    return CodestrataSettings.model_validate(payload)


def check_the_aws_settings_block_keys_are_unchanged() -> CheckResult:
    from codestrata.config.settings import AwsSettings

    actual = tuple(sorted(AwsSettings.model_fields))
    return CheckResult(
        name="the_aws_settings_block_keys_are_unchanged",
        category="configuration",
        ok=actual == AWS_CONFIG_KEYS,
        detail=f"aws_config_keys={list(actual)}",
    )


def check_the_environment_variable_names_are_unchanged() -> CheckResult:
    ok = (
        AWS_PROFILE_ENV_NAME == EXPECTED_PROFILE_ENV_NAME
        and tuple(AWS_REGION_ENV_NAMES) == EXPECTED_REGION_ENV_NAMES
    )
    return CheckResult(
        name="the_documented_aws_environment_variable_names_are_unchanged",
        category="configuration",
        ok=ok,
        detail=f"profile_env={AWS_PROFILE_ENV_NAME} region_envs={list(AWS_REGION_ENV_NAMES)}",
    )


def check_an_explicit_argument_outranks_settings_for_diagnostics() -> CheckResult:
    """The guidance/diagnostics resolver follows the same order as ``aws_config``."""

    settings = settings_with(profile="from-settings", region="from-settings")
    profile = resolve_configured_profile_name(settings=settings, profile_name="from-argument")
    region = resolve_configured_region_name(settings=settings, region_name="from-argument")
    return CheckResult(
        name="an_explicit_profile_or_region_argument_outranks_the_settings_value",
        category="configuration",
        ok=profile == "from-argument" and region == "from-argument",
        detail=f"profile_wins={profile == 'from-argument'} region_wins={region == 'from-argument'}",
    )


def check_the_legacy_bedrock_region_key_is_still_honored() -> CheckResult:
    """``[ai.bedrock].region`` remains the documented fallback behind ``[aws].region``."""

    aws_first = resolve_configured_region_name(
        settings=settings_with(region="from-aws", bedrock_region="from-bedrock")
    )
    bedrock_only = resolve_configured_region_name(
        settings=settings_with(bedrock_region="from-bedrock")
    )
    return CheckResult(
        name="the_aws_region_key_outranks_the_legacy_ai_bedrock_region_key",
        category="configuration",
        ok=aws_first == "from-aws" and bedrock_only == "from-bedrock",
        detail=f"aws_wins={aws_first == 'from-aws'} fallback_used={bedrock_only == 'from-bedrock'}",
    )


def check_the_adapter_never_preresolves_the_credential_chain() -> CheckResult:
    """Settings values must not be promoted into the explicit-argument slot.

    Doing so would silently rank settings above the environment. The client
    inputs must carry the *explicit* arguments verbatim (``None`` when none
    was given) and hand the settings object through separately.
    """

    inputs = build_runtime_configuration(
        settings=settings_with(profile=_PROFILE_VALUE, region=_REGION_VALUE)
    ).client_inputs
    return CheckResult(
        name="settings_values_are_never_promoted_into_the_explicit_argument_slot",
        category="configuration",
        ok=inputs.profile_name is None and inputs.region_name is None,
        detail=(
            f"explicit_profile_is_none={inputs.profile_name is None} "
            f"explicit_region_is_none={inputs.region_name is None}"
        ),
    )


def check_blank_configuration_values_are_treated_as_absent() -> CheckResult:
    inputs = build_runtime_configuration(profile_name="   ", region_name="").client_inputs
    return CheckResult(
        name="whitespace_only_profile_and_region_values_are_treated_as_absent",
        category="configuration",
        ok=not inputs.profile_configured and not inputs.region_configured,
        detail=(
            f"profile_configured={inputs.profile_configured} "
            f"region_configured={inputs.region_configured}"
        ),
    )


def check_the_default_timeout_flows_into_the_client_inputs() -> CheckResult:
    inputs = build_runtime_configuration().client_inputs
    return CheckResult(
        name="the_default_timeout_flows_unchanged_into_the_client_inputs",
        category="configuration",
        ok=inputs.timeout_seconds == EXPECTED_TIMEOUT_SECONDS,
        detail=f"timeout_seconds={inputs.timeout_seconds}",
    )


def check_max_retries_is_represented_but_not_wired() -> CheckResult:
    """CR-1: ``max_retries`` is carried for diagnostics and honored by nothing."""

    from codestrata.ai.provider_adapters.bedrock.factory import BEDROCK_RETRY_POLICY

    settings = settings_with(max_retries=7)
    declared = resolve_max_retries(settings)
    redacted = build_runtime_configuration(settings=settings).redacted()
    return CheckResult(
        name="the_bedrock_max_retries_setting_is_represented_for_diagnostics_but_not_wired",
        category="configuration",
        ok=(
            declared == 7
            and redacted["max_retries_declared"] is True
            and BEDROCK_RETRY_POLICY.maximum_attempts == 1
        ),
        detail=(
            f"max_retries_declared={declared} "
            f"redacted_flag={redacted['max_retries_declared']} "
            f"executor_maximum_attempts={BEDROCK_RETRY_POLICY.maximum_attempts}"
        ),
    )


def check_the_redacted_view_carries_presence_only() -> CheckResult:
    runtime = build_runtime_configuration(
        settings=settings_with(profile=_PROFILE_VALUE, region=_REGION_VALUE)
    )
    rendered = " ".join(
        (
            canonical_json(dict(runtime.redacted())),
            repr(runtime),
            repr(runtime.client_inputs),
        )
    )
    leaked = sorted(
        token for token in (_PROFILE_VALUE, _REGION_VALUE) if token in rendered
    )
    return CheckResult(
        name="the_configuration_view_and_reprs_carry_presence_booleans_not_profile_or_region",
        category="configuration",
        ok=not leaked and runtime.profile_configured and runtime.region_configured,
        detail=f"leaked={leaked}",
    )


def check_building_configuration_touches_no_aws_service() -> CheckResult:
    """Building configuration and an adapter must not construct a client."""

    from verification.bedrock_provider_migration import fixtures

    adapter = build_bedrock_provider(
        settings=settings_with(profile=_PROFILE_VALUE), client=fixtures.Client()
    )
    return CheckResult(
        name="building_configuration_and_an_adapter_constructs_no_aws_client",
        category="configuration",
        ok=adapter.client_injected and adapter.configuration.profile_configured,
        detail="an injected client is used verbatim and aws_config is never called",
    )


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_aws_settings_block_keys_are_unchanged(),
        check_the_environment_variable_names_are_unchanged(),
        check_an_explicit_argument_outranks_settings_for_diagnostics(),
        check_the_legacy_bedrock_region_key_is_still_honored(),
        check_the_adapter_never_preresolves_the_credential_chain(),
        check_blank_configuration_values_are_treated_as_absent(),
        check_the_default_timeout_flows_into_the_client_inputs(),
        check_max_retries_is_represented_but_not_wired(),
        check_the_redacted_view_carries_presence_only(),
        check_building_configuration_touches_no_aws_service(),
    ]
    matrix: dict[str, Any] = {
        "aws_config_keys": list(AWS_CONFIG_KEYS),
        "credential_precedence_owner": "codestrata.ai.aws_config.resolve_aws_config",
        "profile_environment_variable": AWS_PROFILE_ENV_NAME,
        "region_environment_variables": list(AWS_REGION_ENV_NAMES),
        "region_settings_precedence": ["aws.region", "ai.bedrock.region"],
    }
    return checks, matrix


__all__ = [
    "check_an_explicit_argument_outranks_settings_for_diagnostics",
    "check_blank_configuration_values_are_treated_as_absent",
    "check_building_configuration_touches_no_aws_service",
    "check_max_retries_is_represented_but_not_wired",
    "check_the_adapter_never_preresolves_the_credential_chain",
    "check_the_aws_settings_block_keys_are_unchanged",
    "check_the_default_timeout_flows_into_the_client_inputs",
    "check_the_environment_variable_names_are_unchanged",
    "check_the_legacy_bedrock_region_key_is_still_honored",
    "check_the_redacted_view_carries_presence_only",
    "run_configuration_checks",
    "settings_with",
]
