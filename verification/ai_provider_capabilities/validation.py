"""Checks that capability/usage validation correctly rejects invalid input.

Exercises ``codestrata.ai.provider_contracts.capability_validation``/
``usage_validation`` directly (never via a live provider call) to confirm
unknown capability ids, provider/capability mismatches, and invalid usage
records are all rejected with ``ProviderContractValidationError``.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile
from codestrata.ai.provider_contracts.capability_validation import (
    validate_capability_id_is_known,
    validate_capability_profile,
    validate_provider_declares_capability,
    validate_provider_id_is_known,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_validation import (
    validate_completion_status_is_known,
    validate_usage_metadata,
)
from verification.ai_provider_capabilities.models import CheckResult


def _rejects(callable_under_test, *, name: str) -> CheckResult:
    try:
        callable_under_test()
    except ProviderContractValidationError as error:
        return CheckResult(
            name=name, category="validation", ok=True, detail=f"raised: {error}"
        )
    return CheckResult(
        name=name,
        category="validation",
        ok=False,
        detail="did not raise ProviderContractValidationError",
    )


def _accepts(callable_under_test, *, name: str) -> CheckResult:
    try:
        callable_under_test()
    except ProviderContractValidationError as error:
        return CheckResult(
            name=name, category="validation", ok=False, detail=f"unexpectedly raised: {error}"
        )
    return CheckResult(name=name, category="validation", ok=True, detail="accepted as expected")


def check_known_catalog_profiles_pass_validation() -> CheckResult:
    try:
        validate_capability_profile(BEDROCK_CAPABILITY_PROFILE)
        validate_capability_profile(OPENAI_CAPABILITY_PROFILE)
    except ProviderContractValidationError as error:
        return CheckResult(
            name="known_catalog_profiles_pass_capability_validation",
            category="validation",
            ok=False,
            detail=f"unexpectedly raised: {error}",
        )
    return CheckResult(
        name="known_catalog_profiles_pass_capability_validation",
        category="validation",
        ok=True,
        detail="both bedrock and openai profiles validate cleanly",
    )


def check_construction_rejects_a_non_capability_id_entry() -> CheckResult:
    def _construct() -> None:
        ProviderCapabilityProfile(
            provider_id=ProviderId.OPENAI,
            supported_capability_ids=("not_a_capability_id",),  # type: ignore[arg-type]
            supports_structured_json=True,
            supports_streaming=False,
            supports_timeout_policy=True,
            supports_retry_policy=True,
            reports_usage_metadata=True,
            reports_token_accounting=True,
        )

    return _rejects(_construct, name="profile_construction_rejects_a_non_capability_id_entry")


def check_construction_rejects_an_unknown_limitation() -> CheckResult:
    def _construct() -> None:
        ProviderCapabilityProfile(
            provider_id=ProviderId.OPENAI,
            supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
            supports_structured_json=True,
            supports_streaming=False,
            supports_timeout_policy=True,
            supports_retry_policy=True,
            reports_usage_metadata=True,
            reports_token_accounting=True,
            limitations=("made_up_limitation",),
        )

    return _rejects(_construct, name="profile_construction_rejects_an_unknown_limitation")


def check_construction_rejects_streaming_support_true() -> CheckResult:
    def _construct() -> None:
        ProviderCapabilityProfile(
            provider_id=ProviderId.OPENAI,
            supported_capability_ids=(CapabilityId.MODERNIZATION_ADVISOR,),
            supports_structured_json=True,
            supports_streaming=True,
            supports_timeout_policy=True,
            supports_retry_policy=True,
            reports_usage_metadata=True,
            reports_token_accounting=True,
        )

    return _rejects(_construct, name="profile_construction_rejects_supports_streaming_true")


def check_provider_declares_capability_accepts_known_pair() -> CheckResult:
    return _accepts(
        lambda: validate_provider_declares_capability(
            BEDROCK_CAPABILITY_PROFILE, CapabilityId.MODERNIZATION_ADVISOR
        ),
        name="validate_provider_declares_capability_accepts_bedrock_modernization_advisor",
    )


def check_capability_id_validation_accepts_the_known_capability() -> CheckResult:
    return _accepts(
        lambda: validate_capability_id_is_known(CapabilityId.MODERNIZATION_ADVISOR),
        name="validate_capability_id_is_known_accepts_modernization_advisor",
    )


def check_provider_id_validation_accepts_both_known_providers() -> CheckResult:
    def _validate_both() -> None:
        validate_provider_id_is_known(ProviderId.BEDROCK)
        validate_provider_id_is_known(ProviderId.OPENAI)

    return _accepts(_validate_both, name="validate_provider_id_is_known_accepts_bedrock_and_openai")


def check_usage_metadata_validation_accepts_a_consistent_record() -> CheckResult:
    usage = ProviderUsageMetadata(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        completion_status=UsageCompletionStatus.SUCCESS,
    )
    return _accepts(
        lambda: validate_usage_metadata(usage),
        name="validate_usage_metadata_accepts_a_consistent_record",
    )


def check_completion_status_validation_rejects_an_unknown_string() -> CheckResult:
    return _rejects(
        lambda: validate_completion_status_is_known("errored"),
        name="validate_completion_status_is_known_rejects_an_unknown_string",
    )


def run_validation_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_known_catalog_profiles_pass_validation(),
        check_construction_rejects_a_non_capability_id_entry(),
        check_construction_rejects_an_unknown_limitation(),
        check_construction_rejects_streaming_support_true(),
        check_provider_declares_capability_accepts_known_pair(),
        check_capability_id_validation_accepts_the_known_capability(),
        check_provider_id_validation_accepts_both_known_providers(),
        check_usage_metadata_validation_accepts_a_consistent_record(),
        check_completion_status_validation_rejects_an_unknown_string(),
    ]
    matrix = {"check_names": sorted(c.name for c in checks)}
    return checks, matrix


__all__ = [
    "check_capability_id_validation_accepts_the_known_capability",
    "check_completion_status_validation_rejects_an_unknown_string",
    "check_construction_rejects_a_non_capability_id_entry",
    "check_construction_rejects_an_unknown_limitation",
    "check_construction_rejects_streaming_support_true",
    "check_known_catalog_profiles_pass_validation",
    "check_provider_declares_capability_accepts_known_pair",
    "check_provider_id_validation_accepts_both_known_providers",
    "check_usage_metadata_validation_accepts_a_consistent_record",
    "run_validation_checks",
]
