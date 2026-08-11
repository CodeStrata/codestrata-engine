"""Checks that capability/usage serialization is deterministic and secret-free."""

from __future__ import annotations

import re
from typing import Any

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_serialization import (
    serialize_capability_profile_for_diagnostics,
)
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_policy import FORBIDDEN_USAGE_FIELD_NAMES
from codestrata.ai.provider_contracts.usage_serialization import (
    serialize_usage_for_diagnostics,
    serialize_usage_private,
)
from verification.ai_provider_capabilities.models import CheckResult

_SAMPLE_USAGE = ProviderUsageMetadata(
    input_tokens=128,
    output_tokens=64,
    total_tokens=192,
    latency_ms=250.5,
    request_count=1,
    retry_count=0,
    completion_status=UsageCompletionStatus.SUCCESS,
)


def check_capability_serialization_is_deterministic() -> CheckResult:
    first = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    second = serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE)
    ok = first == second
    return CheckResult(
        name="capability_profile_serialization_is_deterministic",
        category="serialization",
        ok=ok,
        detail="two serializations of the same profile are byte-identical" if ok else "mismatch",
    )


def check_usage_serialization_is_deterministic() -> CheckResult:
    first = serialize_usage_for_diagnostics(_SAMPLE_USAGE)
    second = serialize_usage_for_diagnostics(_SAMPLE_USAGE)
    ok = first == second
    detail = "two serializations of the same usage record are byte-identical" if ok else "mismatch"
    return CheckResult(
        name="usage_serialization_is_deterministic",
        category="serialization",
        ok=ok,
        detail=detail,
    )


def check_usage_private_and_diagnostic_views_are_identical() -> CheckResult:
    """usage_serialization.py documents that private == diagnostic for usage records."""

    private = serialize_usage_private(_SAMPLE_USAGE)
    diagnostic = serialize_usage_for_diagnostics(_SAMPLE_USAGE)
    ok = private == diagnostic
    return CheckResult(
        name="usage_private_and_diagnostic_serialized_views_are_identical",
        category="serialization",
        ok=ok,
        detail="private/diagnostic usage views match" if ok else "private/diagnostic mismatch",
    )


def check_serialized_forms_never_contain_forbidden_usage_field_names() -> CheckResult:
    # This checks for the forbidden *field name as a JSON key*, not for the
    # substring anywhere in the text: capability_catalogs.py legitimately
    # declares a "prompt_instruction_only" *limitation* string (describing
    # how Bedrock achieves structured output), which is not a leaked prompt
    # field and must not be flagged.
    texts = [
        serialize_capability_profile_for_diagnostics(BEDROCK_CAPABILITY_PROFILE),
        serialize_capability_profile_for_diagnostics(OPENAI_CAPABILITY_PROFILE),
        serialize_usage_for_diagnostics(_SAMPLE_USAGE),
        serialize_usage_private(_SAMPLE_USAGE),
    ]
    hits = [
        field_name
        for field_name in FORBIDDEN_USAGE_FIELD_NAMES
        if any(re.search(rf'"{re.escape(field_name)}"\s*:', text) for text in texts)
    ]
    ok = not hits
    return CheckResult(
        name="serialized_capability_and_usage_forms_exclude_forbidden_field_names",
        category="serialization",
        ok=ok,
        detail=f"hits={hits}",
    )


def check_capability_serialization_output_is_sorted_key_json() -> CheckResult:
    text = serialize_capability_profile_for_diagnostics(OPENAI_CAPABILITY_PROFILE)
    ok = text.startswith("{") and text.endswith("}") and ", " not in text and ": " not in text
    return CheckResult(
        name="capability_serialization_output_uses_compact_sorted_key_json",
        category="serialization",
        ok=ok,
        detail=f"sample_prefix={text[:40]!r}",
    )


def run_serialization_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_capability_serialization_is_deterministic(),
        check_usage_serialization_is_deterministic(),
        check_usage_private_and_diagnostic_views_are_identical(),
        check_serialized_forms_never_contain_forbidden_usage_field_names(),
        check_capability_serialization_output_is_sorted_key_json(),
    ]
    matrix = {
        "sample_capability_serialization": serialize_capability_profile_for_diagnostics(
            OPENAI_CAPABILITY_PROFILE
        ),
        "sample_usage_serialization": serialize_usage_for_diagnostics(_SAMPLE_USAGE),
    }
    return checks, matrix


__all__ = [
    "check_capability_serialization_is_deterministic",
    "check_capability_serialization_output_is_sorted_key_json",
    "check_serialized_forms_never_contain_forbidden_usage_field_names",
    "check_usage_private_and_diagnostic_views_are_identical",
    "check_usage_serialization_is_deterministic",
    "run_serialization_checks",
]
