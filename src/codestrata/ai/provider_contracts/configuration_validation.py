"""Standalone, reusable validation helpers for the configuration domain.

Every dataclass in this package validates itself in ``__post_init__``; the
functions here expose the same cross-object checks standalone, mirroring
``validation.py`` (Slice 11.2), so callers/tests can validate a fully-built
``AIProviderConfiguration`` (or a raw ``LegacyConfigurationInput``) without
duplicating the rules or constructing throwaway objects just to trigger
``__post_init__``.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.adapter_configuration import (
    validate_adapter_matches_provider,
)
from codestrata.ai.provider_contracts.configuration_compatibility import (
    validate_configuration_version,
)
from codestrata.ai.provider_contracts.configuration_models import AIProviderConfiguration
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

_REQUIRED_SOURCE_TRACE_FIELDS: frozenset[str] = frozenset({"provider_id", "model_reference"})


def validate_ai_provider_configuration(configuration: AIProviderConfiguration) -> None:
    """Re-run every cross-field invariant an ``AIProviderConfiguration`` must satisfy.

    ``AIProviderConfiguration.__post_init__`` already enforces these
    invariants at construction time; this function exists so callers that
    receive an already-constructed configuration (e.g. after a round-trip
    through a mapping) can re-validate it explicitly.
    """

    if not isinstance(configuration, AIProviderConfiguration):
        raise ProviderContractValidationError(
            "configuration must be an AIProviderConfiguration, got "
            f"{type(configuration).__name__}"
        )
    validate_configuration_version(configuration.configuration_version)
    validate_adapter_matches_provider(
        configuration.provider_id, configuration.adapter_configuration
    )

    traced_fields = {item.field_name for item in configuration.source_trace}
    missing = _REQUIRED_SOURCE_TRACE_FIELDS - traced_fields
    if missing:
        raise ProviderContractValidationError(
            f"source_trace is missing required field(s): {sorted(missing)}"
        )

    mismatched = [
        item
        for item in configuration.credential_requirements
        if item.provider_id is not configuration.provider_id
    ]
    if mismatched:
        raise ProviderContractValidationError(
            "every credential_requirement.provider_id must equal configuration.provider_id"
        )

    if not configuration.limitations:
        raise ProviderContractValidationError(
            "limitations must be non-empty for an unwired configuration"
        )


def validate_configuration_is_unwired(configuration: AIProviderConfiguration) -> None:
    """Assert that ``configuration`` carries at least one unwired limitation.

    A defense-in-depth check for tests/verification: an
    ``AIProviderConfiguration`` that reported zero limitations would (falsely)
    imply the configuration is fully wired to real execution.
    """

    if not configuration.limitations:
        raise ProviderContractValidationError(
            "an AIProviderConfiguration built by this slice must always report at least "
            "one limitation (it is never wired to real execution)"
        )


__all__ = [
    "validate_ai_provider_configuration",
    "validate_configuration_is_unwired",
]
