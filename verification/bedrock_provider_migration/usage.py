"""Usage mapping: same token fields, same derivation, same latency preference."""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_adapters.bedrock import usage_mapping
from codestrata.ai.provider_adapters.bedrock.factory import build_bedrock_provider
from codestrata.ai.provider_contracts.usage import UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_policy import FORBIDDEN_USAGE_FIELD_NAMES
from codestrata.ai.providers.bedrock import _extract_usage
from verification.bedrock_provider_migration import fixtures
from verification.bedrock_provider_migration.contract import (
    CONVERSE_LATENCY_FIELD,
    CONVERSE_USAGE_FIELDS,
)
from verification.bedrock_provider_migration.models import CheckResult


def _usage_of(response: Any) -> Any:
    return build_bedrock_provider(client=fixtures.Client(response)).execute(
        fixtures.provider_request()
    ).usage


def check_the_converse_usage_field_names_are_unchanged() -> CheckResult:
    actual = (
        usage_mapping.INPUT_TOKENS_FIELD,
        usage_mapping.OUTPUT_TOKENS_FIELD,
        usage_mapping.TOTAL_TOKENS_FIELD,
    )
    return CheckResult(
        name="the_converse_usage_field_names_are_unchanged",
        category="usage",
        ok=actual == CONVERSE_USAGE_FIELDS
        and usage_mapping.LATENCY_MS_FIELD == CONVERSE_LATENCY_FIELD,
        detail=f"usage_fields={list(actual)} latency_field={usage_mapping.LATENCY_MS_FIELD}",
    )


def check_reported_tokens_are_carried_through() -> CheckResult:
    usage = _usage_of(fixtures.converse_response(input_tokens=11, output_tokens=22))
    return CheckResult(
        name="reported_input_and_output_tokens_are_carried_through_unchanged",
        category="usage",
        ok=usage.input_tokens == 11 and usage.output_tokens == 22,
        detail=f"input_tokens={usage.input_tokens} output_tokens={usage.output_tokens}",
    )


def check_a_missing_total_is_derived() -> CheckResult:
    usage = _usage_of(fixtures.converse_response(input_tokens=4, output_tokens=6))
    return CheckResult(
        name="a_missing_total_token_count_is_still_derived_from_the_two_halves",
        category="usage",
        ok=usage.total_tokens == 10,
        detail=f"total_tokens={usage.total_tokens}",
    )


def check_absent_or_invalid_tokens_become_none() -> CheckResult:
    absent = _usage_of(fixtures.converse_response(include_usage=False))
    invalid = _usage_of(
        fixtures.converse_response(input_tokens=None, output_tokens=None, total_tokens=None)
    )
    negative = usage_mapping.extract_raw_totals({"inputTokens": -1, "outputTokens": "abc"})
    return CheckResult(
        name="absent_negative_and_non_numeric_token_counts_all_become_none",
        category="usage",
        ok=(
            absent.input_tokens is None
            and invalid.input_tokens is None
            and negative.input_tokens is None
            and negative.output_tokens is None
        ),
        detail="coercion tolerance is unchanged",
    )


def check_an_inconsistent_triple_is_reported_verbatim_to_the_legacy_metadata() -> CheckResult:
    """The contract type would reject it; the legacy metadata must still see it."""

    payload = {"inputTokens": 3, "outputTokens": 4, "totalTokens": 99}
    mapped = usage_mapping.map_usage(
        payload, latency_ms=1.0, completion_status=UsageCompletionStatus.SUCCESS
    )
    legacy = _extract_usage(payload)
    return CheckResult(
        name="an_inconsistent_token_triple_is_dropped_from_the_contract_but_reported_verbatim",
        category="usage",
        ok=(
            mapped.total_tokens_dropped
            and mapped.usage.total_tokens is None
            and mapped.raw_totals.total_tokens == 99
            and legacy.total_tokens == 99
        ),
        detail="the legacy ModelUsage is built from the raw totals, so reports are unchanged",
    )


def check_the_reported_latency_wins_over_the_measurement() -> CheckResult:
    usage = _usage_of(fixtures.converse_response(latency_ms=1234))
    return CheckResult(
        name="the_service_reported_latency_is_preferred_over_the_wall_clock_measurement",
        category="usage",
        ok=usage.latency_ms == 1234.0,
        detail=f"latency_ms={usage.latency_ms}",
    )


def check_the_measurement_is_used_when_no_latency_is_reported() -> CheckResult:
    usage = _usage_of(fixtures.converse_response())
    resolved = usage_mapping.resolve_latency_ms(
        reported_latency_ms=None, measured_latency_ms=500.0
    )
    return CheckResult(
        name="the_wall_clock_measurement_is_used_when_the_service_reports_no_latency",
        category="usage",
        ok=usage.latency_ms >= 0.0 and resolved == 500.0,
        detail=f"fallback_latency_ms={resolved}",
    )


def check_an_invalid_reported_latency_falls_back() -> CheckResult:
    values = (
        usage_mapping.extract_reported_latency_ms({"latencyMs": -5}),
        usage_mapping.extract_reported_latency_ms({"latencyMs": "abc"}),
        usage_mapping.extract_reported_latency_ms(None),
    )
    return CheckResult(
        name="a_negative_or_non_numeric_reported_latency_is_ignored",
        category="usage",
        ok=values == (None, None, None),
        detail="an unusable reported latency falls back to the measurement",
    )


def check_a_failure_records_a_token_free_usage() -> CheckResult:
    usage = _usage_of({})
    return CheckResult(
        name="a_failed_invocation_records_usage_with_no_token_counts",
        category="usage",
        ok=(
            usage.input_tokens is None
            and usage.output_tokens is None
            and usage.total_tokens is None
            and usage.completion_status is UsageCompletionStatus.FAILED
        ),
        detail=f"completion_status={usage.completion_status.value}",
    )


def check_usage_records_no_cost_or_billing_field() -> CheckResult:
    usage = _usage_of(fixtures.converse_response())
    offenders = sorted(
        name for name in FORBIDDEN_USAGE_FIELD_NAMES if hasattr(usage, name)
    )
    return CheckResult(
        name="the_usage_record_carries_no_cost_pricing_or_billing_field",
        category="usage",
        ok=not offenders,
        detail=f"offending_fields={offenders}",
        evidence={"forbidden_field_count": len(FORBIDDEN_USAGE_FIELD_NAMES)},
    )


def check_one_call_is_recorded_per_invocation() -> CheckResult:
    usage = _usage_of(fixtures.converse_response())
    return CheckResult(
        name="one_provider_call_and_zero_retries_are_recorded_per_invocation",
        category="usage",
        ok=usage.request_count == 1 and usage.retry_count == 0,
        detail=f"request_count={usage.request_count} retry_count={usage.retry_count}",
    )


def run_usage_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_the_converse_usage_field_names_are_unchanged(),
        check_reported_tokens_are_carried_through(),
        check_a_missing_total_is_derived(),
        check_absent_or_invalid_tokens_become_none(),
        check_an_inconsistent_triple_is_reported_verbatim_to_the_legacy_metadata(),
        check_the_reported_latency_wins_over_the_measurement(),
        check_the_measurement_is_used_when_no_latency_is_reported(),
        check_an_invalid_reported_latency_falls_back(),
        check_a_failure_records_a_token_free_usage(),
        check_usage_records_no_cost_or_billing_field(),
        check_one_call_is_recorded_per_invocation(),
    ]
    matrix: dict[str, Any] = {
        "converse_usage_fields": list(CONVERSE_USAGE_FIELDS),
        "latency_field": CONVERSE_LATENCY_FIELD,
        "latency_preference": ["metrics.latencyMs", "wall_clock_measurement"],
        "total_tokens_derived_when_absent": True,
    }
    return checks, matrix


__all__ = [
    "check_a_failure_records_a_token_free_usage",
    "check_a_missing_total_is_derived",
    "check_absent_or_invalid_tokens_become_none",
    "check_an_inconsistent_triple_is_reported_verbatim_to_the_legacy_metadata",
    "check_an_invalid_reported_latency_falls_back",
    "check_one_call_is_recorded_per_invocation",
    "check_reported_tokens_are_carried_through",
    "check_the_converse_usage_field_names_are_unchanged",
    "check_the_measurement_is_used_when_no_latency_is_reported",
    "check_the_reported_latency_wins_over_the_measurement",
    "check_usage_records_no_cost_or_billing_field",
    "run_usage_checks",
]
