"""Compatibility statements against the Slice 11.1 baseline (CR-1..CR-6).

This module intentionally does **not** import
``verification.ai_provider_baseline`` — a production ``src`` package must
never depend on the repository-local verification tree. Instead, it
restates the six Slice 11.1 compatibility requirement IDs as literals and
records, per requirement, why this contract's type system does not violate
it.

The verification suite (``verification.ai_provider_contracts.
baseline_compatibility``) is responsible for *enforcing* this: it imports
the real ``build_compatibility_requirements()`` from the Slice 11.1 baseline
package and cross-checks that this module's statements cover the exact same
requirement IDs.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.policy import REQUIRED_COMPATIBILITY_REQUIREMENT_IDS


@dataclass(frozen=True, slots=True)
class ContractCompatibilityStatement:
    """A statement that this contract package does or does not violate one CR."""

    requirement_id: str
    holds: bool
    explanation: str


def build_contract_compatibility_statements() -> tuple[ContractCompatibilityStatement, ...]:
    statements = (
        ContractCompatibilityStatement(
            requirement_id="CR-1",
            holds=True,
            explanation=(
                "AIProvider.execute() is a single synchronous call; this contract defines no "
                "retry/fan-out semantics, preserving the exact-one-invoke-per-run expectation "
                "for any future adapter built against it."
            ),
        ),
        ContractCompatibilityStatement(
            requirement_id="CR-2",
            holds=True,
            explanation=(
                "ExecutionOptions.timeout_seconds/temperature/max_tokens are optional and are "
                "not read, wired, or forwarded by anything in this package; no adapter exists "
                "yet, so no settings behavior can have silently changed."
            ),
        ),
        ContractCompatibilityStatement(
            requirement_id="CR-3",
            holds=True,
            explanation=(
                "AIProvider.execute() always returns an AIProviderResult with a status; "
                "provider/parsing/validation failures are represented as FAILED/UNAVAILABLE "
                "results rather than raised exceptions, which is compatible with (but does not "
                "itself implement) fail-soft assess behavior."
            ),
        ),
        ContractCompatibilityStatement(
            requirement_id="CR-4",
            holds=True,
            explanation=(
                "ProviderId values are exactly 'bedrock' and 'openai' — the existing Engine "
                "provider IDs. Analytics provider_family naming ('aws_bedrock') is untouched "
                "and is not represented in this contract."
            ),
        ),
        ContractCompatibilityStatement(
            requirement_id="CR-5",
            holds=True,
            explanation=(
                "AIProviderRegistry.resolve() only calls an explicitly registered zero-argument "
                "factory; constructing requests, results, usage, or registry entries requires no "
                "network access and no credentials."
            ),
        ),
        ContractCompatibilityStatement(
            requirement_id="CR-6",
            holds=True,
            explanation=(
                "This package defines no default provider and no default model ID; "
                "ProviderModelReference is always caller-supplied and opaque."
            ),
        ),
    )
    covered = tuple(sorted(s.requirement_id for s in statements))
    expected = tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))
    if covered != expected:
        raise AssertionError(f"compatibility statements {covered} do not cover expected {expected}")
    return statements


__all__ = [
    "ContractCompatibilityStatement",
    "build_contract_compatibility_statements",
]
