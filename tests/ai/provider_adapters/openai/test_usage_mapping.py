"""Usage mapping: same three wire fields as before, with totals validated."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from codestrata.ai.provider_adapters.openai import usage_mapping
from codestrata.ai.provider_contracts.usage import UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_diagnostics import usage_availability_view
from codestrata.ai.provider_contracts.usage_policy import FORBIDDEN_USAGE_FIELD_NAMES
from tests.ai.provider_adapters.openai import fakes


def test_wire_field_names_match_the_pre_migration_provider() -> None:
    assert usage_mapping.PROMPT_TOKENS_FIELD == "prompt_tokens"
    assert usage_mapping.COMPLETION_TOKENS_FIELD == "completion_tokens"
    assert usage_mapping.TOTAL_TOKENS_FIELD == "total_tokens"


def test_consistent_triple_is_carried_through() -> None:
    totals = usage_mapping.extract_raw_totals(fakes.FakeUsage(10, 20, 30))

    assert (totals.input_tokens, totals.output_tokens, totals.total_tokens) == (10, 20, 30)
    assert totals.consistent


@pytest.mark.parametrize(
    "value",
    [None, "abc", -1, True, False, object(), float("nan")],
)
def test_unusable_token_values_become_none(value: object) -> None:
    assert usage_mapping.optional_non_negative_int(value) is None


def test_float_token_values_are_coerced() -> None:
    assert usage_mapping.optional_non_negative_int(12.0) == 12


def test_missing_usage_object_yields_an_empty_triple() -> None:
    totals = usage_mapping.extract_raw_totals(None)

    assert totals == usage_mapping.RawTokenTotals()
    assert totals.consistent


def test_partial_triple_is_treated_as_consistent() -> None:
    totals = usage_mapping.extract_raw_totals(SimpleNamespace(prompt_tokens=10))

    assert totals.input_tokens == 10
    assert totals.output_tokens is None
    assert totals.consistent


def test_inconsistent_triple_drops_total_but_keeps_raw_totals() -> None:
    mapped = usage_mapping.map_usage(
        fakes.FakeUsage(10, 20, 999),
        latency_ms=5.0,
        completion_status=UsageCompletionStatus.SUCCESS,
    )

    assert mapped.total_tokens_dropped is True
    assert mapped.usage.total_tokens is None
    assert mapped.usage.input_tokens == 10
    assert mapped.usage.output_tokens == 20
    assert mapped.raw_totals.total_tokens == 999


def test_consistent_triple_is_not_dropped() -> None:
    mapped = usage_mapping.map_usage(
        fakes.FakeUsage(10, 20, 30),
        latency_ms=5.0,
        completion_status=UsageCompletionStatus.SUCCESS,
    )

    assert mapped.total_tokens_dropped is False
    assert mapped.usage.total_tokens == 30


def test_negative_latency_is_clamped_to_zero() -> None:
    mapped = usage_mapping.map_usage(
        None, latency_ms=-3.0, completion_status=UsageCompletionStatus.SUCCESS
    )

    assert mapped.usage.latency_ms == 0.0


def test_default_attempt_counts_reflect_a_single_call() -> None:
    mapped = usage_mapping.map_usage(
        None, latency_ms=1.0, completion_status=UsageCompletionStatus.SUCCESS
    )

    assert mapped.usage.request_count == 1
    assert mapped.usage.retry_count == 0


def test_failure_usage_carries_no_tokens() -> None:
    usage = usage_mapping.failure_usage(
        latency_ms=2.0, completion_status=UsageCompletionStatus.FAILED
    )

    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None
    assert usage.completion_status is UsageCompletionStatus.FAILED
    assert usage.latency_ms == 2.0


def test_no_forbidden_cost_or_billing_field_is_produced() -> None:
    mapped = usage_mapping.map_usage(
        fakes.FakeUsage(), latency_ms=1.0, completion_status=UsageCompletionStatus.SUCCESS
    )

    produced = {field.name for field in dataclasses.fields(mapped.usage)}
    produced |= set(usage_availability_view(mapped.usage))
    assert produced.isdisjoint(set(FORBIDDEN_USAGE_FIELD_NAMES))
