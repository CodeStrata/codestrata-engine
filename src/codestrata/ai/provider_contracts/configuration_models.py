"""``AIProviderConfiguration``: the immutable, privacy-preserving configuration envelope.

This is Slice 11.3's central value object. It represents "what
``codestrata assess`` would use for an AI provider," resolved and typed —
but it is never constructed by, or consulted by, the actual assess factory,
providers, enrichment, doctor, or CLI. See ``configuration_projection.py``
for the pure builder function, and
``engine/tests/ai/provider_contracts/test_configuration_runtime_unwired.py``
for the test that proves no product-path file imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.adapter_configuration import (
    AdapterConfiguration,
    validate_adapter_matches_provider,
)
from codestrata.ai.provider_contracts.configuration_compatibility import (
    validate_configuration_version,
)
from codestrata.ai.provider_contracts.configuration_policy import (
    ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES,
    ALLOWED_CREDENTIAL_KINDS,
    CONTRACT_VERSION,
)
from codestrata.ai.provider_contracts.configuration_sources import FieldSource, SourceCategory
from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.identifiers import (
    CapabilityId,
    ProviderId,
    ProviderModelReference,
)
from codestrata.ai.provider_contracts.requests import ExecutionOptions

_REQUIRED_SOURCE_TRACE_FIELDS: frozenset[str] = frozenset({"provider_id", "model_reference"})


@dataclass(frozen=True, slots=True)
class ProviderCredentialRequirement:
    """A credential a provider adapter would need — described abstractly, never as a value.

    ``availability_status`` records whether the credential *appears* to be
    available (e.g. "an environment variable with this name is set") without
    ever inspecting, storing, or forwarding the credential's actual value.
    """

    provider_id: ProviderId
    credential_kind: str
    required: bool
    source_category: SourceCategory
    availability_status: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if self.credential_kind not in ALLOWED_CREDENTIAL_KINDS:
            raise ProviderContractValidationError(
                f"credential_kind must be one of {ALLOWED_CREDENTIAL_KINDS}, "
                f"got {self.credential_kind!r}"
            )
        if not isinstance(self.required, bool):
            raise ProviderContractValidationError("required must be a bool")
        if not isinstance(self.source_category, SourceCategory):
            raise ProviderContractValidationError(
                "source_category must be a SourceCategory, got "
                f"{type(self.source_category).__name__}"
            )
        if self.availability_status not in ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES:
            raise ProviderContractValidationError(
                "availability_status must be one of "
                f"{ALLOWED_CREDENTIAL_AVAILABILITY_STATUSES}, got {self.availability_status!r}"
            )


@dataclass(frozen=True, slots=True)
class AIProviderConfiguration:
    """Immutable, privacy-preserving representation of a resolved AI provider configuration.

    Every field is a typed, validated value object — never a raw settings
    dict, never a credential value. ``source_trace`` must at minimum record
    where ``provider_id`` and ``model_reference`` came from (see
    ``_REQUIRED_SOURCE_TRACE_FIELDS``); ``limitations`` must be non-empty,
    reflecting that this configuration is unwired (see
    ``configuration_projection.UNWIRED_LIMITATIONS``).
    """

    configuration_version: str
    provider_id: ProviderId
    model_reference: ProviderModelReference
    capability_id: CapabilityId
    execution_options: ExecutionOptions
    adapter_configuration: AdapterConfiguration
    source_trace: tuple[FieldSource, ...]
    credential_requirements: tuple[ProviderCredentialRequirement, ...]
    limitations: tuple[str, ...]
    ai_requested: bool | None = None

    def __post_init__(self) -> None:
        validate_configuration_version(self.configuration_version)
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if not isinstance(self.model_reference, ProviderModelReference):
            raise ProviderContractValidationError(
                "model_reference must be a ProviderModelReference, got "
                f"{type(self.model_reference).__name__}"
            )
        if not isinstance(self.capability_id, CapabilityId):
            raise ProviderContractValidationError(
                f"capability_id must be a CapabilityId, got {type(self.capability_id).__name__}"
            )
        if not isinstance(self.execution_options, ExecutionOptions):
            raise ProviderContractValidationError(
                "execution_options must be an ExecutionOptions, got "
                f"{type(self.execution_options).__name__}"
            )
        validate_adapter_matches_provider(self.provider_id, self.adapter_configuration)

        if not isinstance(self.source_trace, tuple) or not all(
            isinstance(item, FieldSource) for item in self.source_trace
        ):
            raise ProviderContractValidationError(
                "source_trace must be a tuple of FieldSource"
            )
        traced_fields = {item.field_name for item in self.source_trace}
        missing = _REQUIRED_SOURCE_TRACE_FIELDS - traced_fields
        if missing:
            raise ProviderContractValidationError(
                f"source_trace is missing required field(s): {sorted(missing)}"
            )

        if not isinstance(self.credential_requirements, tuple) or not all(
            isinstance(item, ProviderCredentialRequirement) for item in self.credential_requirements
        ):
            raise ProviderContractValidationError(
                "credential_requirements must be a tuple of ProviderCredentialRequirement"
            )
        mismatched = [
            item
            for item in self.credential_requirements
            if item.provider_id is not self.provider_id
        ]
        if mismatched:
            raise ProviderContractValidationError(
                "every credential_requirement.provider_id must equal configuration.provider_id"
            )

        if not isinstance(self.limitations, tuple) or not all(
            isinstance(item, str) and item for item in self.limitations
        ):
            raise ProviderContractValidationError(
                "limitations must be a tuple of non-empty strings"
            )
        if not self.limitations:
            raise ProviderContractValidationError(
                "limitations must be non-empty for an unwired configuration"
            )

        if self.ai_requested is not None and not isinstance(self.ai_requested, bool):
            raise ProviderContractValidationError("ai_requested must be a bool or None")


DEFAULT_CONFIGURATION_VERSION = CONTRACT_VERSION


__all__ = [
    "DEFAULT_CONFIGURATION_VERSION",
    "AIProviderConfiguration",
    "ProviderCredentialRequirement",
]
