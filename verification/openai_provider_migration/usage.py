"""Usage mapping: unchanged wire fields, validated totals, no cost or billing data."""

from __future__ import annotations

import dataclasses
from typing import Any

from codestrata.ai.provider_adapters.openai import usage_mapping
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_diagnostics import usage_availability_view
from verification.openai_provider_migration import fixtures
from verification.openai_provider_migration.determinism import canonical_json
from verification.openai_provider_migration.models import CheckResult

_LATENCY_MS = 7.5

# Names that would indicate cost/billing data leaking into usage. Slice 11.3
# deliberately keeps usage token- and latency-only.
_FORBIDDEN_USAGE_FIELD_TOKENS: tuple[str, ...] = (
    "amount",
    "bill",
    "charge",
    "cost",
    "credit",
    "currency",
    "price",
    "spend",
    "usd",
)


def _map(usage_object: Any) -> usage_mapping.MappedUsage:
    return usage_mapping.map_usage(
        usage_object,
        latency_ms=_LATENCY_MS,
        completion_status=UsageCompletionStatus.SUCCESS,
    )


def check_wire_field_names_are_unchanged() -> CheckResult:
    actual = (
        usage_mapping.PROMPT_TOKENS_FIELD,
        usage_mapping.COMPLETION_TOKENS_FIELD,
        usage_mapping.TOTAL_TOKENS_FIELD,
    )
    expected = ("prompt_tokens", "completion_tokens", "total_tokens")
    return CheckResult(
        name="usage_is_still_read_from_prompt_completion_and_total_tokens",
        category="usage",
        ok=actual == expected,
        detail=f"wire_field_names={list(actual)}",
    )


def check_token_totals_are_mapped_onto_the_contract_names() -> CheckResult:
    mapped = _map(fixtures.Usage(prompt_tokens=11, completion_tokens=22, total_tokens=33))
    usage = mapped.usage
    ok = (
        usage.input_tokens == 11
        and usage.output_tokens == 22
        and usage.total_tokens == 33
        and mapped.total_tokens_dropped is False
    )
    return CheckResult(
        name="provider_token_totals_map_onto_input_output_and_total_tokens",
        category="usage",
        ok=ok,
        detail="a consistent triple is carried across unchanged",
    )


def check_an_inconsistent_triple_drops_only_the_total() -> CheckResult:
    mapped = _map(fixtures.Usage(prompt_tokens=10, completion_tokens=20, total_tokens=999))
    usage = mapped.usage
    ok = (
        usage.input_tokens == 10
        and usage.output_tokens == 20
        and usage.total_tokens is None
        and mapped.total_tokens_dropped is True
    )
    return CheckResult(
        name="an_internally_inconsistent_token_triple_drops_only_the_reported_total",
        category="usage",
        ok=ok,
        detail="input/output survive; an impossible total is discarded",
    )


def check_a_partial_triple_is_accepted() -> CheckResult:
    mapped = _map(fixtures.Usage(prompt_tokens=10, completion_tokens=None, total_tokens=None))
    ok = (
        mapped.usage.input_tokens == 10
        and mapped.usage.output_tokens is None
        and mapped.total_tokens_dropped is False
    )
    return CheckResult(
        name="a_partially_reported_token_triple_is_accepted_without_invention",
        category="usage",
        ok=ok,
        detail="missing components stay None rather than being computed",
    )


def check_invalid_token_values_are_discarded() -> CheckResult:
    cases: dict[str, Any] = {
        "negative": fixtures.Usage(prompt_tokens=-5),
        "non_numeric_text": fixtures.Usage(prompt_tokens="many"),
        "boolean": fixtures.Usage(prompt_tokens=True),
        "float_like_text": fixtures.Usage(prompt_tokens="1.5"),
    }
    wrong = sorted(
        name
        for name, usage_object in cases.items()
        if _map(usage_object).usage.input_tokens is not None
    )
    return CheckResult(
        name="negative_boolean_and_non_numeric_token_values_are_discarded",
        category="usage",
        ok=not wrong,
        detail=f"accepted_invalid_cases={wrong}",
        evidence={"cases_compared": sorted(cases)},
    )


def check_a_missing_usage_object_is_tolerated() -> CheckResult:
    mapped = _map(None)
    usage = mapped.usage
    ok = (
        usage.input_tokens is None
        and usage.output_tokens is None
        and usage.total_tokens is None
        and usage.latency_ms == _LATENCY_MS
    )
    return CheckResult(
        name="a_response_without_a_usage_object_still_produces_a_valid_usage_record",
        category="usage",
        ok=ok,
        detail="tokens stay None while latency is still recorded",
    )


def check_failure_usage_is_token_free_but_counted() -> CheckResult:
    usage = usage_mapping.failure_usage(
        latency_ms=_LATENCY_MS, completion_status=UsageCompletionStatus.FAILED
    )
    ok = (
        usage.input_tokens is None
        and usage.total_tokens is None
        and usage.request_count == 1
        and usage.retry_count == 0
        and usage.completion_status is UsageCompletionStatus.FAILED
    )
    return CheckResult(
        name="a_failed_attempt_records_a_counted_token_free_usage_record",
        category="usage",
        ok=ok,
        detail="request_count=1 retry_count=0 with no token data",
    )


def check_negative_latency_is_clamped() -> CheckResult:
    usage = usage_mapping.map_usage(
        fixtures.Usage(),
        latency_ms=-1.0,
        completion_status=UsageCompletionStatus.SUCCESS,
    ).usage
    return CheckResult(
        name="a_negative_measured_latency_is_clamped_to_zero",
        category="usage",
        ok=usage.latency_ms == 0.0,
        detail=f"latency_ms={usage.latency_ms}",
    )


def check_completion_status_reflects_the_execution_status() -> CheckResult:
    statuses = {
        status: usage_mapping.failure_usage(
            latency_ms=0.0, completion_status=status
        ).completion_status
        for status in UsageCompletionStatus
    }
    ok = all(requested is recorded for requested, recorded in statuses.items())
    return CheckResult(
        name="every_usage_completion_status_is_carried_through_unchanged",
        category="usage",
        ok=ok,
        detail=f"statuses={[status.value for status in UsageCompletionStatus]}",
    )


def check_no_cost_or_billing_field_is_produced() -> CheckResult:
    field_names = {field.name for field in dataclasses.fields(ProviderUsageMetadata)}
    view = usage_availability_view(_map(fixtures.Usage()).usage)
    inspected = field_names | set(view)
    offenders = sorted(
        name
        for name in inspected
        if any(token in name.lower() for token in _FORBIDDEN_USAGE_FIELD_TOKENS)
    )
    return CheckResult(
        name="usage_carries_no_cost_currency_or_billing_field",
        category="usage",
        ok=not offenders,
        detail=f"offending_fields={offenders}",
        evidence={"usage_field_names": sorted(field_names)},
    )


def check_the_usage_availability_view_is_value_free() -> CheckResult:
    """The reportable usage view records presence, not token counts."""

    view = usage_availability_view(
        _map(fixtures.Usage(prompt_tokens=4242, completion_tokens=8484, total_tokens=12726)).usage
    )
    serialized = canonical_json(dict(view))
    leaked = sorted(token for token in ("4242", "8484", "12726") if token in serialized)
    return CheckResult(
        name="the_reportable_usage_view_records_availability_rather_than_token_counts",
        category="usage",
        ok=not leaked,
        detail=f"leaked_values={leaked}",
        evidence={"view_keys": sorted(view)},
    )


def run_usage_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_wire_field_names_are_unchanged(),
        check_token_totals_are_mapped_onto_the_contract_names(),
        check_an_inconsistent_triple_drops_only_the_total(),
        check_a_partial_triple_is_accepted(),
        check_invalid_token_values_are_discarded(),
        check_a_missing_usage_object_is_tolerated(),
        check_failure_usage_is_token_free_but_counted(),
        check_negative_latency_is_clamped(),
        check_completion_status_reflects_the_execution_status(),
        check_no_cost_or_billing_field_is_produced(),
        check_the_usage_availability_view_is_value_free(),
    ]
    matrix: dict[str, Any] = {
        "completion_statuses": [status.value for status in UsageCompletionStatus],
        "usage_field_names": sorted(
            field.name for field in dataclasses.fields(ProviderUsageMetadata)
        ),
        "wire_field_names": [
            usage_mapping.PROMPT_TOKENS_FIELD,
            usage_mapping.COMPLETION_TOKENS_FIELD,
            usage_mapping.TOTAL_TOKENS_FIELD,
        ],
    }
    return checks, matrix


__all__ = [
    "check_a_missing_usage_object_is_tolerated",
    "check_a_partial_triple_is_accepted",
    "check_an_inconsistent_triple_drops_only_the_total",
    "check_completion_status_reflects_the_execution_status",
    "check_failure_usage_is_token_free_but_counted",
    "check_invalid_token_values_are_discarded",
    "check_negative_latency_is_clamped",
    "check_no_cost_or_billing_field_is_produced",
    "check_the_usage_availability_view_is_value_free",
    "check_token_totals_are_mapped_onto_the_contract_names",
    "check_wire_field_names_are_unchanged",
    "run_usage_checks",
]
