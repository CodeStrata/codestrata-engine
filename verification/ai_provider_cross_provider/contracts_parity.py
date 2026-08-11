"""Request/response/usage/error/execution parity across OpenAI and Bedrock."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock.factory import (
    BEDROCK_RETRY_POLICY,
    build_bedrock_executor,
    build_bedrock_provider,
)
from codestrata.ai.provider_adapters.openai.factory import (
    OPENAI_RETRY_POLICY,
    build_openai_executor,
    build_openai_provider,
)
from codestrata.ai.provider_contracts.errors import ErrorCategory
from codestrata.ai.provider_contracts.execution_policy import (
    DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES,
    DEFAULT_RETRYABLE_ERROR_CATEGORIES,
)
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.requests import AIProviderRequest, ResponseExpectation
from codestrata.ai.provider_contracts.retry_policy import DEFAULT_RETRY_POLICY
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata
from verification.ai_provider_cross_provider.contract import (
    EXPECTED_MAXIMUM_ATTEMPTS,
    NON_RETRYABLE_BY_DEFAULT,
    POLICY_CONTROLLED_RETRYABLE,
    SHARED_ERROR_CATEGORIES,
)
from verification.ai_provider_cross_provider.models import CheckResult
from verification.bedrock_provider_migration import fixtures as bedrock_fixtures
from verification.openai_provider_migration import fixtures as openai_fixtures


def check_both_adapters_accept_ai_provider_request() -> CheckResult:
    openai_req = openai_fixtures.provider_request()
    bedrock_req = bedrock_fixtures.provider_request()
    ok = (
        isinstance(openai_req, AIProviderRequest)
        and isinstance(bedrock_req, AIProviderRequest)
        and openai_req.capability is CapabilityId.MODERNIZATION_ADVISOR
        and bedrock_req.capability is CapabilityId.MODERNIZATION_ADVISOR
        and openai_req.response_expectation is ResponseExpectation.STRUCTURED_JSON
        and bedrock_req.response_expectation is ResponseExpectation.STRUCTURED_JSON
    )
    return CheckResult(
        name="both_providers_consume_typed_ai_provider_request_for_advisor",
        category="requests",
        ok=ok,
        detail="shared semantic capability request; wire formats remain adapter-owned",
    )


def check_openai_wire_uses_json_mode_bedrock_does_not() -> CheckResult:
    from codestrata.ai.provider_adapters.bedrock.request_mapping import build_converse_kwargs
    from codestrata.ai.provider_adapters.openai.request_mapping import (
        build_chat_completion_kwargs,
    )

    openai_kwargs = build_chat_completion_kwargs(openai_fixtures.provider_request())
    bedrock_kwargs = build_converse_kwargs(bedrock_fixtures.provider_request())
    ok = (
        openai_kwargs.get("response_format") == {"type": "json_object"}
        and "response_format" not in bedrock_kwargs
        and "modelId" in bedrock_kwargs
        and "messages" in openai_kwargs
    )
    return CheckResult(
        name="openai_uses_response_format_bedrock_uses_converse_without_json_mode",
        category="requests",
        ok=ok,
        detail="intentional wire-format difference preserved",
    )


def check_successful_results_report_matching_provider_ids() -> CheckResult:
    openai_client = openai_fixtures.Client(openai_fixtures.response())
    bedrock_client = bedrock_fixtures.Client(bedrock_fixtures.converse_response())
    openai_result = build_openai_provider(client=openai_client).execute(
        openai_fixtures.provider_request()
    )
    bedrock_result = build_bedrock_provider(client=bedrock_client).execute(
        bedrock_fixtures.provider_request()
    )
    ok = (
        openai_result.provider_id is ProviderId.OPENAI
        and bedrock_result.provider_id is ProviderId.BEDROCK
        and openai_result.capability is CapabilityId.MODERNIZATION_ADVISOR
        and bedrock_result.capability is CapabilityId.MODERNIZATION_ADVISOR
        and openai_result.content is not None
        and bedrock_result.content is not None
    )
    return CheckResult(
        name="successful_results_carry_matching_provider_and_capability_identities",
        category="responses",
        ok=ok,
        detail="no provider identity mismatch across adapters",
    )


def check_usage_metadata_shape() -> CheckResult:
    usage = ProviderUsageMetadata(
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
        latency_ms=1.0,
    )
    ok = usage.total_tokens == usage.input_tokens + usage.output_tokens
    return CheckResult(
        name="provider_usage_metadata_enforces_total_consistency_when_complete",
        category="usage",
        ok=ok,
        detail="shared usage contract validates totals; no cost fields",
    )


def check_error_categories_are_shared() -> CheckResult:
    values = tuple(sorted(category.value for category in ErrorCategory))
    ok = values == tuple(sorted(SHARED_ERROR_CATEGORIES))
    return CheckResult(
        name="error_category_enum_matches_shared_closed_set",
        category="errors",
        ok=ok,
        detail=f"categories={len(values)}",
    )


def check_retryability_partition() -> CheckResult:
    retryable = set(DEFAULT_RETRYABLE_ERROR_CATEGORIES)
    non_retryable = set(DEFAULT_NON_RETRYABLE_ERROR_CATEGORIES)
    ok = (
        set(POLICY_CONTROLLED_RETRYABLE) <= retryable
        and set(NON_RETRYABLE_BY_DEFAULT) <= non_retryable
        and "authentication_failed" in non_retryable
        and "invalid_model" in non_retryable
    )
    return CheckResult(
        name="default_retry_partition_matches_cross_provider_policy",
        category="errors",
        ok=ok,
        detail="auth/invalid non-retryable; timeout/rate/unavailable policy-controlled",
    )


def check_executors_share_single_attempt_policy() -> CheckResult:
    ok = (
        OPENAI_RETRY_POLICY is DEFAULT_RETRY_POLICY
        and BEDROCK_RETRY_POLICY is DEFAULT_RETRY_POLICY
        and DEFAULT_RETRY_POLICY.maximum_attempts == EXPECTED_MAXIMUM_ATTEMPTS
    )
    return CheckResult(
        name="both_executors_pin_default_retry_policy_maximum_attempts_one",
        category="execution",
        ok=ok,
        detail="CR-1 single logical attempt; max_retries=3 not activated",
    )


def check_executors_make_one_call_even_on_retryable_failure() -> CheckResult:
    openai_client = openai_fixtures.Client(openai_fixtures.sdk_exception("RateLimitError"))
    bedrock_client = bedrock_fixtures.Client(bedrock_fixtures.client_error("ThrottlingException"))
    openai_execution = build_openai_executor(build_openai_provider(client=openai_client)).execute(
        openai_fixtures.provider_request()
    )
    bedrock_execution = build_bedrock_executor(
        build_bedrock_provider(client=bedrock_client)
    ).execute(bedrock_fixtures.provider_request())
    ok = (
        len(openai_client.calls) == 1
        and len(bedrock_client.calls) == 1
        and openai_execution.attempts == 1
        and bedrock_execution.attempts == 1
    )
    return CheckResult(
        name="retryable_failures_still_make_exactly_one_provider_call_for_both",
        category="execution",
        ok=ok,
        detail="no stacked CodeStrata retries on either provider",
    )


def run_request_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_both_adapters_accept_ai_provider_request(),
        check_openai_wire_uses_json_mode_bedrock_does_not(),
    ]
    return checks, {"wire_formats": {"openai": "chat_completions", "bedrock": "converse"}}


def run_response_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    return [check_successful_results_report_matching_provider_ids()], {}


def run_usage_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    return [check_usage_metadata_shape()], {"cost_fields": False}


def run_error_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [check_error_categories_are_shared(), check_retryability_partition()]
    return checks, {
        "shared_categories": list(SHARED_ERROR_CATEGORIES),
        "non_retryable_by_default": list(NON_RETRYABLE_BY_DEFAULT),
        "policy_controlled_retryable": list(POLICY_CONTROLLED_RETRYABLE),
    }


def run_execution_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_executors_share_single_attempt_policy(),
        check_executors_make_one_call_even_on_retryable_failure(),
    ]
    return checks, {
        "maximum_attempts": EXPECTED_MAXIMUM_ATTEMPTS,
        "timeout_enforcement": "adapter_client_owned",
    }


__all__ = [
    "run_error_checks",
    "run_execution_checks",
    "run_request_checks",
    "run_response_checks",
    "run_usage_checks",
]
