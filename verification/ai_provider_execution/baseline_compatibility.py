"""Cross-check the execution domain against the real, loaded Slice 11.1 baseline.

This is the one place in the Slice 11.4 verification suite that imports
``verification.ai_provider_baseline`` — the verification tree is allowed to
depend on another verification package; the new *production* modules
(``codestrata.ai.provider_contracts.execution_*``) never do (see
``dependency_boundary.py``).
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.execution_compatibility import (
    build_execution_compatibility_statements,
)
from codestrata.ai.provider_contracts.execution_policy import (
    DEFAULT_MAXIMUM_ATTEMPTS,
    DEFAULT_TIMEOUT_SECONDS,
    SETTINGS_DEFAULT_MAX_RETRIES,
)
from codestrata.ai.provider_contracts.retry_policy import (
    DEFAULT_RETRY_POLICY,
    SETTINGS_REPRESENTABLE_RETRY_POLICY,
    max_retries_to_maximum_attempts,
)
from verification.ai_provider_baseline.reporting import build_compatibility_requirements
from verification.ai_provider_execution.contract import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from verification.ai_provider_execution.models import CheckResult


def check_baseline_defines_exactly_six_requirements() -> CheckResult:
    requirements = build_compatibility_requirements()
    ids = tuple(r.requirement_id for r in requirements)
    ok = ids == REQUIRED_COMPATIBILITY_REQUIREMENT_IDS
    return CheckResult(
        name="slice_11_1_baseline_defines_cr1_through_cr6",
        category="baseline_compatibility",
        ok=ok,
        detail=f"ids={ids}",
    )


def check_execution_statements_cover_every_baseline_requirement() -> CheckResult:
    requirements = build_compatibility_requirements()
    baseline_ids = {r.requirement_id for r in requirements}
    statements = build_execution_compatibility_statements()
    statement_ids = {s.requirement_id for s in statements}
    ok = baseline_ids == statement_ids
    return CheckResult(
        name="execution_compatibility_statements_cover_every_baseline_requirement",
        category="baseline_compatibility",
        ok=ok,
        detail=f"baseline_ids={sorted(baseline_ids)} statement_ids={sorted(statement_ids)}",
    )


def check_every_compatibility_statement_holds() -> CheckResult:
    statements = build_execution_compatibility_statements()
    failing = [s.requirement_id for s in statements if not s.holds]
    ok = not failing
    return CheckResult(
        name="every_execution_compatibility_statement_holds_true",
        category="baseline_compatibility",
        ok=ok,
        detail=f"failing={failing}",
    )


def check_default_retry_policy_matches_cr1_exact_one_invoke() -> CheckResult:
    """CR-1: the default retry policy makes exactly one attempt (no CodeStrata-level retries)."""

    ok = DEFAULT_RETRY_POLICY.maximum_attempts == 1 == DEFAULT_MAXIMUM_ATTEMPTS
    return CheckResult(
        name="default_retry_policy_maximum_attempts_is_one_matching_cr1",
        category="baseline_compatibility",
        ok=ok,
        detail=f"maximum_attempts={DEFAULT_RETRY_POLICY.maximum_attempts}",
    )


def check_settings_representable_retry_policy_matches_real_settings_default() -> CheckResult:
    """SETTINGS_REPRESENTABLE_RETRY_POLICY must represent max_retries=3 -> maximum_attempts=4."""

    from codestrata.config.settings import BedrockSettings, OpenAISettings

    real_bedrock_default = BedrockSettings.model_fields["max_retries"].default
    real_openai_default = OpenAISettings.model_fields["max_retries"].default
    expected_attempts = max_retries_to_maximum_attempts(SETTINGS_DEFAULT_MAX_RETRIES)
    ok = (
        real_bedrock_default == real_openai_default == SETTINGS_DEFAULT_MAX_RETRIES
        and SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts == expected_attempts
    )
    return CheckResult(
        name="settings_representable_retry_policy_matches_real_bedrock_and_openai_max_retries",
        category="baseline_compatibility",
        ok=ok,
        detail=(
            f"real_bedrock_max_retries={real_bedrock_default} "
            f"real_openai_max_retries={real_openai_default} "
            f"literal={SETTINGS_DEFAULT_MAX_RETRIES} "
            f"represented_maximum_attempts={SETTINGS_REPRESENTABLE_RETRY_POLICY.maximum_attempts}"
        ),
    )


def check_default_timeout_seconds_matches_real_providers_default() -> CheckResult:
    from codestrata.ai.providers.models import DEFAULT_TIMEOUT_SECONDS as REAL_DEFAULT_TIMEOUT

    ok = DEFAULT_TIMEOUT_SECONDS == REAL_DEFAULT_TIMEOUT
    return CheckResult(
        name="execution_policy_default_timeout_seconds_matches_real_providers_default",
        category="baseline_compatibility",
        ok=ok,
        detail=f"literal={DEFAULT_TIMEOUT_SECONDS} real={REAL_DEFAULT_TIMEOUT}",
    )


def run_baseline_compatibility_checks() -> tuple[list[CheckResult], dict[str, Any]]:
    checks = [
        check_baseline_defines_exactly_six_requirements(),
        check_execution_statements_cover_every_baseline_requirement(),
        check_every_compatibility_statement_holds(),
        check_default_retry_policy_matches_cr1_exact_one_invoke(),
        check_settings_representable_retry_policy_matches_real_settings_default(),
        check_default_timeout_seconds_matches_real_providers_default(),
    ]
    requirements = build_compatibility_requirements()
    statements = build_execution_compatibility_statements()
    matrix = {
        "requirement_ids": sorted(r.requirement_id for r in requirements),
        "statement_holds_by_requirement_id": {
            s.requirement_id: s.holds for s in sorted(statements, key=lambda s: s.requirement_id)
        },
    }
    return checks, matrix


__all__ = [
    "check_baseline_defines_exactly_six_requirements",
    "check_default_retry_policy_matches_cr1_exact_one_invoke",
    "check_default_timeout_seconds_matches_real_providers_default",
    "check_every_compatibility_statement_holds",
    "check_execution_statements_cover_every_baseline_requirement",
    "check_settings_representable_retry_policy_matches_real_settings_default",
    "run_baseline_compatibility_checks",
]
