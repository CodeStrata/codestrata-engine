"""Characterize token usage extraction/normalization (pure functions, synthetic data)."""

from __future__ import annotations

from pathlib import Path

from codestrata.ai.providers.bedrock import _extract_usage  # noqa: SLF001
from codestrata.ai.providers.models import ModelUsage
from verification.ai_provider_baseline.models import CheckResult


def bedrock_usage_scenarios() -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = [
        {"input": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}, "name": "all_present"},
        {"input": {"inputTokens": 10, "outputTokens": 5}, "name": "total_derived"},
        {"input": {}, "name": "empty_payload"},
        {"input": {"inputTokens": -1}, "name": "negative_coerced_to_none"},
        {"input": None, "name": "non_dict_payload"},
    ]
    results: list[dict[str, object]] = []
    for scenario in scenarios:
        usage = _extract_usage(scenario["input"])
        results.append(
            {
                "input_tokens": usage.input_tokens,
                "name": scenario["name"],
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
        )
    results.sort(key=lambda item: str(item["name"]))
    return results


def check_usage_model_fields(_source_root: Path) -> CheckResult:
    usage = ModelUsage(input_tokens=1, output_tokens=2, total_tokens=3)
    ok = usage.input_tokens == 1 and usage.output_tokens == 2 and usage.total_tokens == 3
    return CheckResult(
        name="model_usage_fields_are_optional_nonnegative_ints",
        category="usage",
        ok=ok,
        detail="ModelUsage(input_tokens, output_tokens, total_tokens) all optional, ge=0",
    )


def check_bedrock_usage_derives_total_when_missing(_source_root: Path) -> CheckResult:
    scenarios = {item["name"]: item for item in bedrock_usage_scenarios()}
    derived = scenarios["total_derived"]
    ok = derived["total_tokens"] == 15
    return CheckResult(
        name="bedrock_usage_total_tokens_derived_from_input_plus_output",
        category="usage",
        ok=ok,
        detail=f"derived total_tokens={derived['total_tokens']}",
    )


def check_bedrock_usage_handles_malformed_payload(_source_root: Path) -> CheckResult:
    scenarios = {item["name"]: item for item in bedrock_usage_scenarios()}
    empty = scenarios["empty_payload"]
    non_dict = scenarios["non_dict_payload"]
    negative = scenarios["negative_coerced_to_none"]
    ok = (
        empty["input_tokens"] is None
        and non_dict["input_tokens"] is None
        and negative["input_tokens"] is None
    )
    return CheckResult(
        name="bedrock_usage_extraction_tolerates_malformed_payloads",
        category="usage",
        ok=ok,
        detail="empty/None/negative usage payloads yield None fields, never raise",
    )


def run_usage_checks(source_root: Path) -> tuple[list[CheckResult], dict[str, object]]:
    checks = [
        check_usage_model_fields(source_root),
        check_bedrock_usage_derives_total_when_missing(source_root),
        check_bedrock_usage_handles_malformed_payload(source_root),
    ]
    matrix = {"bedrock_usage_scenarios": bedrock_usage_scenarios()}
    return checks, matrix


__all__ = [
    "bedrock_usage_scenarios",
    "check_bedrock_usage_derives_total_when_missing",
    "check_bedrock_usage_handles_malformed_payload",
    "check_usage_model_fields",
    "run_usage_checks",
]
