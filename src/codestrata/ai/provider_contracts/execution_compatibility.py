"""Compatibility statements against the Slice 11.1 baseline (CR-1..CR-6), plus version helpers.

Mirrors ``compatibility.py`` (Slice 11.2) / ``configuration_compatibility.py``
(Slice 11.3): this module intentionally does **not** import
``verification.ai_provider_baseline`` — a production ``src`` package must
never depend on the repository-local verification tree. The verification
suite (``verification.ai_provider_execution.baseline_compatibility``) is
responsible for *enforcing* this: it imports the real
``build_compatibility_requirements()`` from the Slice 11.1 baseline package
and cross-checks that this module's statements cover the exact same
requirement IDs.

The version helpers below (``SUPPORTED_EXECUTION_VERSIONS``,
``validate_execution_version``) are a distinct version namespace from
``versions.CURRENT_CONTRACT_VERSION`` (Slice 11.2) and
``configuration_compatibility.SUPPORTED_CONFIGURATION_VERSIONS`` (Slice
11.3), even though all three currently happen to equal ``"1.0"``. No type in
this slice actually carries an ``execution_version`` field today — these
helpers exist so a future execution-result-shaped value object can adopt
the same versioning convention without inventing a new pattern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.execution_policy import (
    CONTRACT_VERSION,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)

_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

SUPPORTED_EXECUTION_VERSIONS: tuple[str, ...] = (CONTRACT_VERSION,)


def is_supported_execution_version(value: str) -> bool:
    return value in SUPPORTED_EXECUTION_VERSIONS


def validate_execution_version(value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.match(value):
        raise ProviderContractValidationError(
            f"execution_version must match '<major>.<minor>', got {value!r}"
        )
    if not is_supported_execution_version(value):
        raise ProviderContractValidationError(
            f"unsupported execution_version {value!r}; supported: {SUPPORTED_EXECUTION_VERSIONS}"
        )


@dataclass(frozen=True, slots=True)
class ExecutionCompatibilityStatement:
    """A statement that the execution domain does or does not violate one CR."""

    requirement_id: str
    holds: bool
    explanation: str


def build_execution_compatibility_statements() -> tuple[ExecutionCompatibilityStatement, ...]:
    statements = (
        ExecutionCompatibilityStatement(
            requirement_id="CR-1",
            holds=True,
            explanation=(
                "DEFAULT_RETRY_POLICY.maximum_attempts=1 makes AIProviderExecutor call "
                "AIProvider.execute() exactly once by default, preserving the existing "
                "exact-one-invoke-per-assess-run contract; SETTINGS_REPRESENTABLE_RETRY_POLICY "
                "(maximum_attempts=4) is a pure representation, is never the executor's "
                "default, and is used by nothing."
            ),
        ),
        ExecutionCompatibilityStatement(
            requirement_id="CR-2",
            holds=True,
            explanation=(
                "TimeoutPolicy/AIProviderRetryPolicy are optional, unwired value objects; "
                "nothing in this slice reads settings.ai.bedrock/openai.timeout_seconds/"
                "max_retries and forwards them to AIProviderExecutor, and the executor never "
                "reads os.environ or a settings object itself — the existing silent "
                "non-wiring documented by Slice 11.1 "
                "(SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY=False) is unchanged."
            ),
        ),
        ExecutionCompatibilityStatement(
            requirement_id="CR-3",
            holds=True,
            explanation=(
                "AIProviderExecutor.execute() never raises for a provider's FAILED/UNAVAILABLE "
                "AIProviderResult, and it also catches any unexpected Exception raised by "
                "AIProvider.execute() itself, converting it into a FAILED result classified as "
                "internal_failure rather than propagating — strictly more fail-soft than the "
                "AIProvider protocol already requires. It is never called by codestrata assess, "
                "so it cannot change assess's real exit-code behavior."
            ),
        ),
        ExecutionCompatibilityStatement(
            requirement_id="CR-4",
            holds=True,
            explanation=(
                "AIProviderExecutionResult.provider_id reuses ProviderId unchanged from Slice "
                "11.2; the executor validates that AIProvider.execute()'s returned "
                "provider_id matches provider.provider_id but never introduces a new "
                "provider identifier."
            ),
        ),
        ExecutionCompatibilityStatement(
            requirement_id="CR-5",
            holds=True,
            explanation=(
                "AIProviderExecutor never reads os.environ, never reads a file, and never "
                "constructs a provider client or network connection; every dependency "
                "(provider, clock, sleeper, timeout/retry/backoff policy) is injected by the "
                "caller, so this slice's own tests/verification run fully offline against fakes."
            ),
        ),
        ExecutionCompatibilityStatement(
            requirement_id="CR-6",
            holds=True,
            explanation=(
                "This slice defines no default provider and no default model ID; "
                "DEFAULT_TIMEOUT_SECONDS (60.0) and SETTINGS_DEFAULT_MAX_RETRIES (3) are "
                "literal restatements of the real, unchanged settings defaults "
                "(BedrockSettings/OpenAISettings), cross-checked by verification, not new "
                "values chosen by this slice."
            ),
        ),
    )
    covered = tuple(sorted(s.requirement_id for s in statements))
    expected = tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))
    if covered != expected:
        raise AssertionError(
            f"execution compatibility statements {covered} do not cover expected {expected}"
        )
    return statements


__all__ = [
    "SUPPORTED_EXECUTION_VERSIONS",
    "ExecutionCompatibilityStatement",
    "build_execution_compatibility_statements",
    "is_supported_execution_version",
    "validate_execution_version",
]
