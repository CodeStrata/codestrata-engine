"""Adapter-configuration type-safety and no-invented-field checks."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.adapter_configuration import (
    BedrockAdapterConfiguration,
    OpenAIAdapterConfiguration,
    validate_adapter_matches_provider,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import ProviderId
from verification.ai_provider_configuration.models import CheckResult

# Fields that would indicate an invented setting not present on the real
# Bedrock/OpenAI settings surface (see engine/docs/ai-provider-configuration.md
# ground truth: no organization, project, or Bedrock endpoint_url exist today).
_FORBIDDEN_INVENTED_FIELDS: frozenset[str] = frozenset(
    {"organization", "project", "endpoint_url", "org_id", "project_id"}
)


def check_openai_adapter_has_no_invented_fields() -> CheckResult:
    fields = {f.name for f in OpenAIAdapterConfiguration.__dataclass_fields__.values()}
    invented = sorted(fields & _FORBIDDEN_INVENTED_FIELDS)
    ok = not invented
    return CheckResult(
        name="openai_adapter_configuration_has_no_invented_fields",
        category="adapter_configuration",
        ok=ok,
        detail=f"invented={invented} fields={sorted(fields)}",
    )


def check_bedrock_adapter_has_no_invented_fields() -> CheckResult:
    fields = {f.name for f in BedrockAdapterConfiguration.__dataclass_fields__.values()}
    invented = sorted(fields & _FORBIDDEN_INVENTED_FIELDS)
    ok = not invented
    return CheckResult(
        name="bedrock_adapter_configuration_has_no_invented_fields",
        category="adapter_configuration",
        ok=ok,
        detail=f"invented={invented} fields={sorted(fields)}",
    )


def check_adapter_type_mismatch_is_rejected() -> CheckResult:
    mismatches_rejected = 0
    for provider_id, wrong_adapter in (
        (ProviderId.OPENAI, BedrockAdapterConfiguration()),
        (ProviderId.BEDROCK, OpenAIAdapterConfiguration()),
    ):
        try:
            validate_adapter_matches_provider(provider_id, wrong_adapter)
        except ProviderContractValidationError:
            mismatches_rejected += 1
    ok = mismatches_rejected == 2
    return CheckResult(
        name="adapter_configuration_type_mismatch_is_always_rejected",
        category="adapter_configuration",
        ok=ok,
        detail=f"mismatches_rejected={mismatches_rejected}/2",
    )


def check_adapter_type_match_is_accepted() -> CheckResult:
    try:
        validate_adapter_matches_provider(ProviderId.OPENAI, OpenAIAdapterConfiguration())
        validate_adapter_matches_provider(ProviderId.BEDROCK, BedrockAdapterConfiguration())
    except ProviderContractValidationError as error:
        return CheckResult(
            name="adapter_configuration_type_match_is_accepted",
            category="adapter_configuration",
            ok=False,
            detail=f"unexpectedly rejected a matching pairing: {error}",
        )
    return CheckResult(
        name="adapter_configuration_type_match_is_accepted",
        category="adapter_configuration",
        ok=True,
        detail="both matching pairings were accepted",
    )


def run_adapter_configuration_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_openai_adapter_has_no_invented_fields(),
        check_bedrock_adapter_has_no_invented_fields(),
        check_adapter_type_mismatch_is_rejected(),
        check_adapter_type_match_is_accepted(),
    ]
    matrix = {"forbidden_invented_fields": sorted(_FORBIDDEN_INVENTED_FIELDS)}
    return checks, matrix


__all__ = [
    "check_adapter_type_match_is_accepted",
    "check_adapter_type_mismatch_is_rejected",
    "check_bedrock_adapter_has_no_invented_fields",
    "check_openai_adapter_has_no_invented_fields",
    "run_adapter_configuration_checks",
]
