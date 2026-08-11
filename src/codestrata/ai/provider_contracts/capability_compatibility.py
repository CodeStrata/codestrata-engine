"""Compatibility statements against Slice 11.1 (CR-1..CR-6) and Slices 11.2-11.4.

Mirrors ``compatibility.py`` (Slice 11.2)/``configuration_compatibility.py``
(Slice 11.3)/``execution_compatibility.py`` (Slice 11.4): this module
intentionally does **not** import ``verification.ai_provider_baseline`` — a
production ``src`` package must never depend on the repository-local
verification tree. Instead it restates the six Slice 11.1 compatibility
requirement IDs as literals and records, per requirement, why the
*capability discovery and usage metadata* types in this slice do not violate
it.

The verification suite (``verification.ai_provider_capabilities.
compatibility``) is responsible for *enforcing* the CR-1..CR-6 statements: it
imports the real ``build_compatibility_requirements()`` from the Slice 11.1
baseline package and cross-checks that this module's statements cover the
exact same requirement IDs. This module also carries a second, distinct set
of statements — :func:`build_prior_slice_compatibility_notes` — recording
that this slice does not modify anything Slices 11.2/11.3/11.4 shipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.capability_policy import (
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)


@dataclass(frozen=True, slots=True)
class CapabilityCompatibilityStatement:
    """A statement that the capability/usage domain does or does not violate one CR."""

    requirement_id: str
    holds: bool
    explanation: str


def build_capability_compatibility_statements() -> tuple[CapabilityCompatibilityStatement, ...]:
    statements = (
        CapabilityCompatibilityStatement(
            requirement_id="CR-1",
            holds=True,
            explanation=(
                "ProviderCapabilityProfile and ProviderUsageMetadata are read-only, "
                "declared-only value objects; neither is consulted by AIProvider.execute() "
                "or AIProviderExecutor, so the exact-one-invoke-per-assess-run contract is "
                "unaffected."
            ),
        ),
        CapabilityCompatibilityStatement(
            requirement_id="CR-2",
            holds=True,
            explanation=(
                "supports_timeout_policy/supports_retry_policy are declaration-only booleans "
                "(both carry the 'not_wired_to_runtime' limitation in capability_catalogs.py); "
                "nothing in this slice reads settings.ai.bedrock/openai.timeout_seconds/"
                "max_retries or forwards them anywhere, so the existing silent non-wiring "
                "documented by Slice 11.1 is unchanged."
            ),
        ),
        CapabilityCompatibilityStatement(
            requirement_id="CR-3",
            holds=True,
            explanation=(
                "Constructing a ProviderCapabilityProfile/ProviderUsageMetadata only raises "
                "ProviderContractValidationError for malformed input to this package's own "
                "pure constructors; neither type is on any path codestrata assess executes, "
                "so it cannot introduce a new way for `codestrata assess` to exit non-zero."
            ),
        ),
        CapabilityCompatibilityStatement(
            requirement_id="CR-4",
            holds=True,
            explanation=(
                "capability_catalogs.py declares profiles for exactly ProviderId.BEDROCK and "
                "ProviderId.OPENAI, re-using the Slice 11.2 identifiers.ProviderId enum "
                "unchanged; no new provider identifier or analytics provider_family label is "
                "introduced."
            ),
        ),
        CapabilityCompatibilityStatement(
            requirement_id="CR-5",
            holds=True,
            explanation=(
                "Every function in capability_catalogs.py/capability_validation.py/"
                "capability_serialization.py takes already-constructed value objects as "
                "arguments; none of them read os.environ, read a file, or make a network call."
            ),
        ),
        CapabilityCompatibilityStatement(
            requirement_id="CR-6",
            holds=True,
            explanation=(
                "This slice defines no default provider and no default model ID; "
                "capability_catalogs.py declares capability profiles only, never a preferred "
                "or default provider selection."
            ),
        ),
    )
    covered = tuple(sorted(s.requirement_id for s in statements))
    expected = tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))
    if covered != expected:
        raise AssertionError(
            f"capability compatibility statements {covered} do not cover expected {expected}"
        )
    return statements


@dataclass(frozen=True, slots=True)
class PriorSliceCompatibilityNote:
    """A statement that this slice does not modify a specific prior Slice 11.x deliverable."""

    slice_id: str
    holds: bool
    explanation: str


def build_prior_slice_compatibility_notes() -> tuple[PriorSliceCompatibilityNote, ...]:
    notes = (
        PriorSliceCompatibilityNote(
            slice_id="11.2",
            holds=True,
            explanation=(
                "capabilities.py's CAPABILITY_PAYLOAD_TYPES and ModernizationAdvisorInput are "
                "untouched; capability_models.py/capability_catalogs.py/capability_policy.py "
                "are new sibling modules that only import identifiers.py/errors.py/policy.py "
                "from Slice 11.2, never the other way around."
            ),
        ),
        PriorSliceCompatibilityNote(
            slice_id="11.3",
            holds=True,
            explanation=(
                "No configuration_*/adapter_configuration.py/model_configuration.py/"
                "legacy_configuration.py module is imported by, or imports, any Slice 11.5 "
                "module; provider/model configuration resolution is completely unaffected."
            ),
        ),
        PriorSliceCompatibilityNote(
            slice_id="11.4",
            holds=True,
            explanation=(
                "No execution_*/executor.py/timeout_policy.py/retry_policy.py/"
                "retry_decision.py/backoff.py/error_classification.py module is imported by, "
                "or imports, any Slice 11.5 module; AIProviderExecutor's fail-soft retry/"
                "timeout behavior is completely unaffected. supports_timeout_policy/"
                "supports_retry_policy describe TimeoutPolicy/AIProviderRetryPolicy only as "
                "documentation, never by importing execution_policy.py's concrete types."
            ),
        ),
    )
    return notes


__all__ = [
    "CapabilityCompatibilityStatement",
    "PriorSliceCompatibilityNote",
    "build_capability_compatibility_statements",
    "build_prior_slice_compatibility_notes",
]
