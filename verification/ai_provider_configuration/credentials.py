"""Credential-requirement shape checks: never a value, always a bounded kind/status."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.configuration_policy import (
    ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES,
    ALLOWED_CREDENTIAL_KINDS,
)
from codestrata.ai.provider_contracts.configuration_projection import project_configuration
from codestrata.ai.provider_contracts.legacy_configuration import LegacyConfigurationInput
from verification.ai_provider_configuration.models import CheckResult


def check_openai_requires_an_api_key_credential() -> CheckResult:
    configuration = project_configuration(
        LegacyConfigurationInput(provider="openai", openai_api_key_present=False)
    )
    kinds = {item.credential_kind for item in configuration.credential_requirements}
    ok = kinds == {"api_key"}
    return CheckResult(
        name="openai_configuration_declares_exactly_one_api_key_credential_requirement",
        category="credentials",
        ok=ok,
        detail=f"kinds={sorted(kinds)}",
    )


def check_openai_absent_api_key_is_reported_as_absent() -> CheckResult:
    configuration = project_configuration(
        LegacyConfigurationInput(provider="openai", openai_api_key_present=False)
    )
    statuses = {item.availability_status for item in configuration.credential_requirements}
    ok = statuses == {"absent"}
    return CheckResult(
        name="openai_configuration_reports_absent_api_key_availability_correctly",
        category="credentials",
        ok=ok,
        detail=f"statuses={sorted(statuses)}",
    )


def check_bedrock_requires_default_credential_chain() -> CheckResult:
    configuration = project_configuration(LegacyConfigurationInput(provider="bedrock"))
    kinds = {item.credential_kind for item in configuration.credential_requirements}
    ok = "aws_default_chain" in kinds
    return CheckResult(
        name="bedrock_configuration_declares_an_aws_default_chain_credential_requirement",
        category="credentials",
        ok=ok,
        detail=f"kinds={sorted(kinds)}",
    )


def check_bedrock_profile_adds_an_optional_profile_credential() -> CheckResult:
    without_profile = project_configuration(
        LegacyConfigurationInput(provider="bedrock", bedrock_profile_configured=False)
    )
    with_profile = project_configuration(
        LegacyConfigurationInput(provider="bedrock", bedrock_profile_configured=True)
    )
    ok = (
        "aws_profile" not in {i.credential_kind for i in without_profile.credential_requirements}
        and "aws_profile" in {i.credential_kind for i in with_profile.credential_requirements}
    )
    return CheckResult(
        name="bedrock_profile_configured_adds_an_optional_aws_profile_credential_requirement",
        category="credentials",
        ok=ok,
        detail=(
            f"without={sorted(i.credential_kind for i in without_profile.credential_requirements)} "
            f"with={sorted(i.credential_kind for i in with_profile.credential_requirements)}"
        ),
    )


def check_no_credential_requirement_field_can_carry_a_value() -> CheckResult:
    from codestrata.ai.provider_contracts.configuration_models import ProviderCredentialRequirement

    fields = {f.name for f in ProviderCredentialRequirement.__dataclass_fields__.values()}
    forbidden = {"value", "secret", "api_key", "password", "token"}
    ok = fields.isdisjoint(forbidden)
    return CheckResult(
        name="provider_credential_requirement_has_no_value_carrying_field",
        category="credentials",
        ok=ok,
        detail=f"fields={sorted(fields)}",
    )


def check_credential_kinds_and_statuses_are_bounded() -> CheckResult:
    for provider, kwargs in (
        ("openai", {"provider": "openai", "openai_api_key_present": True}),
        ("bedrock", {"provider": "bedrock", "bedrock_profile_configured": True}),
    ):
        configuration = project_configuration(LegacyConfigurationInput(**kwargs))
        for item in configuration.credential_requirements:
            if item.credential_kind not in ALLOWED_CREDENTIAL_KINDS:
                return CheckResult(
                    name="every_credential_requirement_uses_an_allowed_kind_and_status",
                    category="credentials",
                    ok=False,
                    detail=f"unexpected credential_kind {item.credential_kind!r} for {provider}",
                )
            if item.availability_status not in ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES:
                return CheckResult(
                    name="every_credential_requirement_uses_an_allowed_kind_and_status",
                    category="credentials",
                    ok=False,
                    detail=(
                        f"unexpected availability_status {item.availability_status!r} "
                        f"for {provider}"
                    ),
                )
    return CheckResult(
        name="every_credential_requirement_uses_an_allowed_kind_and_status",
        category="credentials",
        ok=True,
        detail="all credential requirements used bounded kind/status values",
    )


def run_credential_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openai_requires_an_api_key_credential(),
        check_openai_absent_api_key_is_reported_as_absent(),
        check_bedrock_requires_default_credential_chain(),
        check_bedrock_profile_adds_an_optional_profile_credential(),
        check_no_credential_requirement_field_can_carry_a_value(),
        check_credential_kinds_and_statuses_are_bounded(),
    ]
    matrix = {
        "allowed_credential_kinds": list(ALLOWED_CREDENTIAL_KINDS),
        "allowed_availability_statuses": list(ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES),
    }
    return checks, matrix


__all__ = [
    "check_bedrock_profile_adds_an_optional_profile_credential",
    "check_bedrock_requires_default_credential_chain",
    "check_credential_kinds_and_statuses_are_bounded",
    "check_no_credential_requirement_field_can_carry_a_value",
    "check_openai_absent_api_key_is_reported_as_absent",
    "check_openai_requires_an_api_key_credential",
    "run_credential_checks",
]
