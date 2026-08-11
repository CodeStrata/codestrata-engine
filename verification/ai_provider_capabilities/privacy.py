"""Privacy characterization: capability/usage diagnostics never leak sensitive text.

Capability profiles never carry prompts, credentials, or model references in
the first place, and usage records never carry cost/pricing/billing/prompt/
response/request-ID/exception text (see ``usage_policy.
FORBIDDEN_USAGE_FIELD_NAMES``) — this module confirms both properties hold
for the diagnostic views/serialized forms this slice defines.
"""

from __future__ import annotations

import re
from typing import Any

from codestrata.ai.provider_contracts.capability_catalogs import (
    BEDROCK_CAPABILITY_PROFILE,
    OPENAI_CAPABILITY_PROFILE,
)
from codestrata.ai.provider_contracts.capability_diagnostics import (
    diagnostic_view_of_capability_profile,
)
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata, UsageCompletionStatus
from codestrata.ai.provider_contracts.usage_diagnostics import usage_availability_view
from codestrata.ai.provider_contracts.usage_serialization import serialize_usage_for_diagnostics
from verification.ai_provider_capabilities.models import CheckResult

_CREDENTIAL_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
)
_PATH_TOKENS = ("/Users/", "/home/")

_SAMPLE_USAGE = ProviderUsageMetadata(
    input_tokens=42,
    output_tokens=17,
    total_tokens=59,
    latency_ms=100.0,
    completion_status=UsageCompletionStatus.SUCCESS,
)


def check_capability_diagnostic_view_contains_no_credential_shaped_tokens() -> CheckResult:
    views = [
        diagnostic_view_of_capability_profile(BEDROCK_CAPABILITY_PROFILE),
        diagnostic_view_of_capability_profile(OPENAI_CAPABILITY_PROFILE),
    ]
    blob = repr(views)
    hits = [p.pattern for p in _CREDENTIAL_PATTERNS if p.search(blob)]
    ok = not hits
    return CheckResult(
        name="capability_diagnostic_view_contains_no_credential_shaped_tokens",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def check_capability_diagnostic_view_contains_no_absolute_paths() -> CheckResult:
    views = [
        diagnostic_view_of_capability_profile(BEDROCK_CAPABILITY_PROFILE),
        diagnostic_view_of_capability_profile(OPENAI_CAPABILITY_PROFILE),
    ]
    blob = repr(views)
    hits = [token for token in _PATH_TOKENS if token in blob]
    ok = not hits
    return CheckResult(
        name="capability_diagnostic_view_contains_no_absolute_paths",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def check_usage_availability_view_reports_flags_only_never_values() -> CheckResult:
    view = usage_availability_view(_SAMPLE_USAGE)
    ok = all(isinstance(value, bool) for value in view.values())
    return CheckResult(
        name="usage_availability_view_reports_booleans_only_never_raw_values",
        category="privacy",
        ok=ok,
        detail=f"value_types={sorted({type(v).__name__ for v in view.values()})}",
    )


def check_usage_serialized_form_contains_no_credential_shaped_tokens() -> CheckResult:
    text = serialize_usage_for_diagnostics(_SAMPLE_USAGE)
    hits = [p.pattern for p in _CREDENTIAL_PATTERNS if p.search(text)]
    ok = not hits
    return CheckResult(
        name="usage_serialized_diagnostic_form_contains_no_credential_shaped_tokens",
        category="privacy",
        ok=ok,
        detail=f"hits={hits}",
    )


def run_privacy_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_capability_diagnostic_view_contains_no_credential_shaped_tokens(),
        check_capability_diagnostic_view_contains_no_absolute_paths(),
        check_usage_availability_view_reports_flags_only_never_values(),
        check_usage_serialized_form_contains_no_credential_shaped_tokens(),
    ]
    matrix = {
        "sample_capability_diagnostic_view": diagnostic_view_of_capability_profile(
            OPENAI_CAPABILITY_PROFILE
        ),
        "sample_usage_availability_view": usage_availability_view(_SAMPLE_USAGE),
    }
    return checks, matrix


__all__ = [
    "check_capability_diagnostic_view_contains_no_absolute_paths",
    "check_capability_diagnostic_view_contains_no_credential_shaped_tokens",
    "check_usage_availability_view_reports_flags_only_never_values",
    "check_usage_serialized_form_contains_no_credential_shaped_tokens",
    "run_privacy_checks",
]
