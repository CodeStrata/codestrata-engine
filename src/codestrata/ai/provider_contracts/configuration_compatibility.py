"""Compatibility statements against the Slice 11.1 baseline (CR-1..CR-6), plus version helpers.

Mirrors ``compatibility.py`` (Slice 11.2): this module intentionally does
**not** import ``verification.ai_provider_baseline`` — a production ``src``
package must never depend on the repository-local verification tree.
Instead it restates the six Slice 11.1 compatibility requirement IDs as
literals and records, per requirement, why the *configuration* domain types
in this slice do not violate it.

The verification suite
(``verification.ai_provider_configuration.baseline_compatibility``) is
responsible for *enforcing* this: it imports the real
``build_compatibility_requirements()`` from the Slice 11.1 baseline package
and cross-checks that this module's statements cover the exact same
requirement IDs.

The version helpers below (``SUPPORTED_CONFIGURATION_VERSIONS``,
``validate_configuration_version``) govern
``AIProviderConfiguration.configuration_version`` — a distinct version
namespace from ``codestrata.ai.provider_contracts.versions.
CURRENT_CONTRACT_VERSION`` (Slice 11.2's request/response envelope
version), even though both currently happen to equal ``"1.0"``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.ai.provider_contracts.configuration_policy import (
    CONTRACT_VERSION,
    REQUIRED_COMPATIBILITY_REQUIREMENT_IDS,
)
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

# Slice 11.3 supports exactly one configuration contract version. Future
# slices may extend this to a tuple of accepted versions with an explicit
# migration note.
SUPPORTED_CONFIGURATION_VERSIONS: tuple[str, ...] = (CONTRACT_VERSION,)


def is_supported_configuration_version(value: str) -> bool:
    return value in SUPPORTED_CONFIGURATION_VERSIONS


def validate_configuration_version(value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.match(value):
        raise ProviderContractValidationError(
            f"configuration_version must match '<major>.<minor>', got {value!r}"
        )
    if not is_supported_configuration_version(value):
        raise ProviderContractValidationError(
            f"unsupported configuration_version {value!r}; supported: "
            f"{SUPPORTED_CONFIGURATION_VERSIONS}"
        )


@dataclass(frozen=True, slots=True)
class ConfigurationCompatibilityStatement:
    """A statement that the configuration domain does or does not violate one CR."""

    requirement_id: str
    holds: bool
    explanation: str


def build_configuration_compatibility_statements() -> (
    tuple[ConfigurationCompatibilityStatement, ...]
):
    statements = (
        ConfigurationCompatibilityStatement(
            requirement_id="CR-1",
            holds=True,
            explanation=(
                "AIProviderConfiguration is a resolved, read-only snapshot; it defines no "
                "retry/fan-out semantics and is never consulted by AiEnrichmentService.run(), "
                "so the exact-one-invoke-per-assess-run contract is unaffected."
            ),
        ),
        ConfigurationCompatibilityStatement(
            requirement_id="CR-2",
            holds=True,
            explanation=(
                "timeout_seconds/max_retries are represented (on ExecutionOptions and on the "
                "adapter configurations) purely as optional, unwired data — nothing in this "
                "slice reads settings.ai.bedrock/openai.timeout_seconds/max_retries and forwards "
                "them to any provider call; the existing silent non-wiring documented by Slice "
                "11.1 (SETTINGS_TIMEOUT_MAX_RETRIES_WIRED_TO_ASSESS_FACTORY=False) is unchanged."
            ),
        ),
        ConfigurationCompatibilityStatement(
            requirement_id="CR-3",
            holds=True,
            explanation=(
                "Building an AIProviderConfiguration only raises ProviderContractValidationError "
                "for malformed *input* to this package's own pure functions; it is never called "
                "by codestrata assess, so it cannot introduce a new way for `codestrata assess` "
                "to exit non-zero on an AI failure."
            ),
        ),
        ConfigurationCompatibilityStatement(
            requirement_id="CR-4",
            holds=True,
            explanation=(
                "resolve_provider_id()/ProviderId values are exactly 'bedrock' and 'openai' — "
                "the existing Engine provider IDs, re-used unchanged from Slice 11.2's "
                "identifiers.py. Analytics provider_family naming ('aws_bedrock') is untouched."
            ),
        ),
        ConfigurationCompatibilityStatement(
            requirement_id="CR-5",
            holds=True,
            explanation=(
                "Every resolution function (resolve_provider_id, resolve_model_reference, "
                "legacy_configuration_input_from_mapping, project_configuration) takes "
                "already-extracted plain values as arguments; none of them read os.environ, "
                "read a file, or construct a provider client/network connection."
            ),
        ),
        ConfigurationCompatibilityStatement(
            requirement_id="CR-6",
            holds=True,
            explanation=(
                "DEFAULT_PROVIDER_ID ('bedrock') and DEFAULT_MODEL_BY_PROVIDER "
                "('amazon.nova-lite-v1:0' / 'gpt-4o-mini') are literal restatements of the real "
                "production defaults, not new values; this slice changes none of them, and "
                "verification cross-checks them against the loaded Slice 11.1 baseline."
            ),
        ),
    )
    covered = tuple(sorted(s.requirement_id for s in statements))
    expected = tuple(sorted(REQUIRED_COMPATIBILITY_REQUIREMENT_IDS))
    if covered != expected:
        raise AssertionError(
            f"configuration compatibility statements {covered} do not cover expected {expected}"
        )
    return statements


__all__ = [
    "SUPPORTED_CONFIGURATION_VERSIONS",
    "ConfigurationCompatibilityStatement",
    "build_configuration_compatibility_statements",
    "is_supported_configuration_version",
    "validate_configuration_version",
]
