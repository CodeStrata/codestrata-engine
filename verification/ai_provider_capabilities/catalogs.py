"""Checks on the static, unwired baseline capability catalogs (bedrock, openai, openrouter)."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    KNOWN_PROVIDER_CAPABILITY_PROFILES,
    OPENAI_CAPABILITY_PROFILE,
    OPENROUTER_CAPABILITY_PROFILE,
    all_known_capability_profiles,
    capability_profile_for,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from verification.ai_provider_capabilities.contract import KNOWN_CAPABILITY_PROVIDER_IDS
from verification.ai_provider_capabilities.models import CheckResult


def check_exactly_bedrock_and_openai_are_cataloged() -> CheckResult:
    provider_ids = tuple(sorted(p.value for p in KNOWN_PROVIDER_CAPABILITY_PROFILES))
    ok = provider_ids == tuple(sorted(KNOWN_CAPABILITY_PROVIDER_IDS))
    return CheckResult(
        name="capability_catalog_covers_bedrock_openai_and_openrouter",
        category="catalogs",
        ok=ok,
        detail=f"provider_ids={provider_ids}",
    )


def check_both_providers_declare_modernization_advisor() -> CheckResult:
    ok = (
        BEDROCK_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)
        and OPENAI_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)
        and OPENROUTER_CAPABILITY_PROFILE.declares_capability(CapabilityId.MODERNIZATION_ADVISOR)
    )
    return CheckResult(
        name="both_catalog_profiles_declare_modernization_advisor",
        category="catalogs",
        ok=ok,
        detail=(
            f"bedrock={BEDROCK_CAPABILITY_PROFILE.supported_capability_ids} "
            f"openai={OPENAI_CAPABILITY_PROFILE.supported_capability_ids} "
            f"openrouter={OPENROUTER_CAPABILITY_PROFILE.supported_capability_ids}"
        ),
    )


def check_structured_json_reflects_intentional_slice_11_1_difference() -> CheckResult:
    """OpenAI has a native JSON mode; Bedrock's structured output is prompt-only."""

    ok = (
        OPENAI_CAPABILITY_PROFILE.supports_structured_json is True
        and BEDROCK_CAPABILITY_PROFILE.supports_structured_json is False
        and "prompt_instruction_only" in BEDROCK_CAPABILITY_PROFILE.limitations
    )
    return CheckResult(
        name="structured_json_support_reflects_intentional_openai_bedrock_difference",
        category="catalogs",
        ok=ok,
        detail=(
            f"openai_json={OPENAI_CAPABILITY_PROFILE.supports_structured_json} "
            f"bedrock_json={BEDROCK_CAPABILITY_PROFILE.supports_structured_json} "
            f"bedrock_limitations={BEDROCK_CAPABILITY_PROFILE.limitations}"
        ),
    )


def check_neither_provider_declares_streaming_support() -> CheckResult:
    ok = (
        BEDROCK_CAPABILITY_PROFILE.supports_streaming is False
        and OPENAI_CAPABILITY_PROFILE.supports_streaming is False
        and OPENROUTER_CAPABILITY_PROFILE.supports_streaming is False
    )
    return CheckResult(
        name="neither_catalog_profile_declares_streaming_support",
        category="catalogs",
        ok=ok,
        detail=(
            f"bedrock={BEDROCK_CAPABILITY_PROFILE.supports_streaming} "
            f"openai={OPENAI_CAPABILITY_PROFILE.supports_streaming} "
            f"openrouter={OPENROUTER_CAPABILITY_PROFILE.supports_streaming}"
        ),
    )


def check_timeout_and_retry_policy_flags_carry_not_wired_limitation() -> CheckResult:
    """supports_timeout_policy/supports_retry_policy are contract-readiness flags only."""

    profiles = (BEDROCK_CAPABILITY_PROFILE, OPENAI_CAPABILITY_PROFILE)
    ok = all(
        profile.supports_timeout_policy is True
        and profile.supports_retry_policy is True
        and "not_wired_to_runtime" in profile.limitations
        for profile in profiles
    )
    return CheckResult(
        name="timeout_and_retry_policy_support_flags_carry_not_wired_to_runtime_limitation",
        category="catalogs",
        ok=ok,
        detail=f"limitations={[p.limitations for p in profiles]}",
    )


def check_both_providers_report_usage_and_token_accounting() -> CheckResult:
    profiles = (
        BEDROCK_CAPABILITY_PROFILE,
        OPENAI_CAPABILITY_PROFILE,
        OPENROUTER_CAPABILITY_PROFILE,
    )
    ok = all(
        profile.reports_usage_metadata is True and profile.reports_token_accounting is True
        for profile in profiles
    )
    return CheckResult(
        name="both_catalog_profiles_report_usage_metadata_and_token_accounting",
        category="catalogs",
        ok=ok,
        detail=(
            f"bedrock=({BEDROCK_CAPABILITY_PROFILE.reports_usage_metadata}, "
            f"{BEDROCK_CAPABILITY_PROFILE.reports_token_accounting}) "
            f"openai=({OPENAI_CAPABILITY_PROFILE.reports_usage_metadata}, "
            f"{OPENAI_CAPABILITY_PROFILE.reports_token_accounting}) "
            f"openrouter=({OPENROUTER_CAPABILITY_PROFILE.reports_usage_metadata}, "
            f"{OPENROUTER_CAPABILITY_PROFILE.reports_token_accounting})"
        ),
    )


def check_capability_profile_for_lookup_matches_direct_reference() -> CheckResult:
    ok = (
        capability_profile_for(ProviderId.BEDROCK) is BEDROCK_CAPABILITY_PROFILE
        and capability_profile_for(ProviderId.OPENAI) is OPENAI_CAPABILITY_PROFILE
        and capability_profile_for(ProviderId.OPENROUTER) is OPENROUTER_CAPABILITY_PROFILE
    )
    return CheckResult(
        name="capability_profile_for_returns_the_expected_static_profile",
        category="catalogs",
        ok=ok,
        detail="capability_profile_for(provider_id) identity-matches the module constant",
    )


def check_all_known_capability_profiles_is_deterministic() -> CheckResult:
    first = tuple(str(p.provider_id) for p in all_known_capability_profiles())
    second = tuple(str(p.provider_id) for p in all_known_capability_profiles())
    ok = first == second == tuple(sorted(first))
    return CheckResult(
        name="all_known_capability_profiles_returns_a_stable_sorted_order",
        category="catalogs",
        ok=ok,
        detail=f"first={first} second={second}",
    )


def run_catalog_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_exactly_bedrock_and_openai_are_cataloged(),
        check_both_providers_declare_modernization_advisor(),
        check_structured_json_reflects_intentional_slice_11_1_difference(),
        check_neither_provider_declares_streaming_support(),
        check_timeout_and_retry_policy_flags_carry_not_wired_limitation(),
        check_both_providers_report_usage_and_token_accounting(),
        check_capability_profile_for_lookup_matches_direct_reference(),
        check_all_known_capability_profiles_is_deterministic(),
    ]
    matrix = {
        "bedrock_profile": {
            "limitations": sorted(BEDROCK_CAPABILITY_PROFILE.limitations),
            "supports_structured_json": BEDROCK_CAPABILITY_PROFILE.supports_structured_json,
        },
        "openai_profile": {
            "limitations": sorted(OPENAI_CAPABILITY_PROFILE.limitations),
            "supports_structured_json": OPENAI_CAPABILITY_PROFILE.supports_structured_json,
        },
    }
    return checks, matrix


__all__ = [
    "check_all_known_capability_profiles_is_deterministic",
    "check_both_providers_declare_modernization_advisor",
    "check_both_providers_report_usage_and_token_accounting",
    "check_capability_profile_for_lookup_matches_direct_reference",
    "check_exactly_bedrock_and_openai_are_cataloged",
    "check_neither_provider_declares_streaming_support",
    "check_structured_json_reflects_intentional_slice_11_1_difference",
    "check_timeout_and_retry_policy_flags_carry_not_wired_limitation",
    "run_catalog_checks",
]
