"""Configuration: unchanged keys, unchanged defaults, and redacted projections."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.openai import configuration as adapter_configuration
from codestrata.ai.provider_adapters.openai.factory import (
    build_openai_provider,
    resolve_openai_settings,
)
from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS
from codestrata.config import CodestrataSettings
from codestrata.config.settings import OpenAISettings
from verification.openai_provider_migration.contract import (
    EXPECTED_TIMEOUT_SECONDS,
    OPENAI_API_KEY_ENV_DEFAULT,
    OPENAI_CONFIG_KEYS,
)
from verification.openai_provider_migration.determinism import canonical_json
from verification.openai_provider_migration.models import CheckResult

_SYNTHETIC_BASE_URL = "https://synthetic-gateway.invalid/v1"
_SYNTHETIC_KEY_VAR = "SYNTHETIC_OPENAI_KEY_VAR"


def check_openai_config_keys_are_unchanged() -> CheckResult:
    actual = tuple(sorted(OpenAISettings.model_fields))
    expected = tuple(sorted(OPENAI_CONFIG_KEYS))
    return CheckResult(
        name="openai_settings_config_keys_are_unchanged",
        category="configuration",
        ok=actual == expected,
        detail=f"config_keys={list(actual)}",
    )


def check_api_key_env_default_is_unchanged() -> CheckResult:
    default_from_settings = OpenAISettings().api_key_env
    default_from_adapter = adapter_configuration.DEFAULT_API_KEY_ENV_NAME
    resolved = adapter_configuration.resolve_api_key_env_name(None)
    ok = (
        default_from_settings
        == default_from_adapter
        == resolved
        == OPENAI_API_KEY_ENV_DEFAULT
    )
    return CheckResult(
        name="openai_api_key_environment_variable_default_is_unchanged",
        category="configuration",
        ok=ok,
        detail=f"api_key_env={default_from_settings} adapter_default={default_from_adapter}",
    )


def check_custom_api_key_env_is_honored() -> CheckResult:
    resolved = adapter_configuration.resolve_api_key_env_name(
        OpenAISettings(api_key_env=_SYNTHETIC_KEY_VAR)
    )
    return CheckResult(
        name="custom_api_key_environment_variable_name_is_honored",
        category="configuration",
        ok=resolved == _SYNTHETIC_KEY_VAR,
        detail="a configured api_key_env name is used verbatim",
    )


def check_base_url_is_optional_and_normalized() -> CheckResult:
    absent = adapter_configuration.resolve_base_url(OpenAISettings())
    present = adapter_configuration.resolve_base_url(
        OpenAISettings(base_url=f"  {_SYNTHETIC_BASE_URL} ")
    )
    ok = absent is None and present == _SYNTHETIC_BASE_URL
    return CheckResult(
        name="optional_base_url_is_normalized_and_defaults_to_absent",
        category="configuration",
        ok=ok,
        detail="blank/absent base_url resolves to None; a configured value is stripped",
    )


def check_default_timeout_is_unchanged() -> CheckResult:
    runtime = adapter_configuration.build_runtime_configuration()
    ok = (
        runtime.client_inputs.timeout_seconds
        == DEFAULT_TIMEOUT_SECONDS
        == EXPECTED_TIMEOUT_SECONDS
    )
    return CheckResult(
        name="default_provider_request_timeout_is_still_sixty_seconds",
        category="configuration",
        ok=ok,
        detail=f"timeout_seconds={runtime.client_inputs.timeout_seconds}",
    )


def check_settings_precedence_is_preserved() -> CheckResult:
    """An explicit settings block wins; otherwise the tree; otherwise defaults."""

    tree = CodestrataSettings.model_validate(
        {
            "repository": {"path": "."},
            "ai": {"provider": "openai", "openai": {"api_key_env": "FROM_TREE_VAR"}},
        }
    )
    explicit = resolve_openai_settings(
        settings=tree, openai_settings=OpenAISettings(api_key_env=_SYNTHETIC_KEY_VAR)
    )
    from_tree = resolve_openai_settings(settings=tree)
    fallback = resolve_openai_settings()
    ok = (
        explicit.api_key_env == _SYNTHETIC_KEY_VAR
        and from_tree.api_key_env == "FROM_TREE_VAR"
        and fallback.api_key_env == OPENAI_API_KEY_ENV_DEFAULT
    )
    return CheckResult(
        name="openai_settings_resolution_precedence_is_preserved",
        category="configuration",
        ok=ok,
        detail="explicit block > settings tree > OpenAISettings() defaults",
    )


def check_redacted_configuration_hides_the_base_url() -> CheckResult:
    runtime = adapter_configuration.build_runtime_configuration(
        openai_settings=OpenAISettings(base_url=_SYNTHETIC_BASE_URL)
    )
    view = runtime.redacted()
    serialized = canonical_json(dict(view))
    ok = (
        "synthetic-gateway" not in serialized
        and view.get("base_url_configured") is True
        and "synthetic-gateway" not in repr(runtime)
        and "synthetic-gateway" not in repr(runtime.client_inputs)
    )
    return CheckResult(
        name="redacted_configuration_reports_base_url_presence_but_never_its_value",
        category="configuration",
        ok=ok,
        detail="redacted() and __repr__ report base_url_configured only",
    )


def check_api_key_presence_is_not_resolved_by_configuration() -> CheckResult:
    """Key presence is only ever decided at the credential boundary in client.py."""

    runtime = adapter_configuration.build_runtime_configuration()
    return CheckResult(
        name="configuration_never_resolves_api_key_presence_itself",
        category="configuration",
        ok=runtime.adapter_configuration.api_key_present is False,
        detail="api_key_present defaults to False without an explicit caller assertion",
    )


def check_adapter_configuration_is_reachable_for_diagnostics() -> CheckResult:
    adapter = build_openai_provider(
        openai_settings=OpenAISettings(api_key_env=_SYNTHETIC_KEY_VAR)
    )
    return CheckResult(
        name="adapter_exposes_its_resolved_configuration_for_diagnostics",
        category="configuration",
        ok=adapter.configuration.api_key_env_name == _SYNTHETIC_KEY_VAR,
        detail="OpenAIProvider.configuration.api_key_env_name reflects the resolved settings",
    )


def run_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openai_config_keys_are_unchanged(),
        check_api_key_env_default_is_unchanged(),
        check_custom_api_key_env_is_honored(),
        check_base_url_is_optional_and_normalized(),
        check_default_timeout_is_unchanged(),
        check_settings_precedence_is_preserved(),
        check_redacted_configuration_hides_the_base_url(),
        check_api_key_presence_is_not_resolved_by_configuration(),
        check_adapter_configuration_is_reachable_for_diagnostics(),
    ]
    matrix: dict[str, Any] = {
        "api_key_env_default": OPENAI_API_KEY_ENV_DEFAULT,
        "config_keys": list(OPENAI_CONFIG_KEYS),
        "default_timeout_seconds": EXPECTED_TIMEOUT_SECONDS,
        "redacted_configuration_field_names": sorted(
            adapter_configuration.build_runtime_configuration().redacted()
        ),
    }
    return checks, matrix


__all__ = [
    "check_adapter_configuration_is_reachable_for_diagnostics",
    "check_api_key_env_default_is_unchanged",
    "check_api_key_presence_is_not_resolved_by_configuration",
    "check_base_url_is_optional_and_normalized",
    "check_custom_api_key_env_is_honored",
    "check_default_timeout_is_unchanged",
    "check_openai_config_keys_are_unchanged",
    "check_redacted_configuration_hides_the_base_url",
    "check_settings_precedence_is_preserved",
    "run_configuration_checks",
]
