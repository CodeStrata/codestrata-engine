"""The immutable AI provider result envelope."""

from __future__ import annotations

from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import (
    AIProviderError,
    ProviderContractValidationError,
)
from codestrata.ai.provider_contracts.execution import ProviderExecutionStatus
from codestrata.ai.provider_contracts.identifiers import CapabilityId, ProviderId
from codestrata.ai.provider_contracts.usage import ProviderUsageMetadata
from codestrata.ai.provider_contracts.versions import (
    CURRENT_CONTRACT_VERSION,
    validate_contract_version,
)

_MAX_TEXT_LENGTH = 2_000_000


@dataclass(frozen=True, slots=True)
class AIProviderResultContent:
    """Typed result content: free text and/or a provider-neutral JSON payload.

    ``structured_payload`` is a plain ``dict`` of already-decoded JSON (not a
    provider SDK object); it represents "the capability's parsed structured
    output," not any single provider's wire response.
    """

    text: str | None = None
    structured_payload: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.text is not None:
            if not isinstance(self.text, str):
                raise ProviderContractValidationError("text must be a string when present")
            if len(self.text) > _MAX_TEXT_LENGTH:
                raise ProviderContractValidationError("text exceeds the maximum length")
        if self.structured_payload is not None and not isinstance(self.structured_payload, dict):
            raise ProviderContractValidationError("structured_payload must be a dict when present")
        if self.text is None and self.structured_payload is None:
            raise ProviderContractValidationError(
                "AIProviderResultContent requires at least one of text/structured_payload"
            )


@dataclass(frozen=True, slots=True)
class AIProviderResult:
    """Immutable result of a single provider-contract execution request."""

    provider_id: ProviderId
    capability: CapabilityId
    status: ProviderExecutionStatus
    contract_version: str = CURRENT_CONTRACT_VERSION.value
    content: AIProviderResultContent | None = None
    usage: ProviderUsageMetadata | None = None
    error: AIProviderError | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        if not isinstance(self.provider_id, ProviderId):
            raise ProviderContractValidationError(
                f"provider_id must be a ProviderId, got {type(self.provider_id).__name__}"
            )
        if not isinstance(self.capability, CapabilityId):
            raise ProviderContractValidationError(
                f"capability must be a CapabilityId, got {type(self.capability).__name__}"
            )
        if not isinstance(self.status, ProviderExecutionStatus):
            raise ProviderContractValidationError(
                f"status must be a ProviderExecutionStatus, got {type(self.status).__name__}"
            )
        if self.content is not None and not isinstance(self.content, AIProviderResultContent):
            raise ProviderContractValidationError(
                "content must be an AIProviderResultContent when present"
            )
        if self.usage is not None and not isinstance(self.usage, ProviderUsageMetadata):
            raise ProviderContractValidationError(
                "usage must be a ProviderUsageMetadata when present"
            )
        if self.error is not None and not isinstance(self.error, AIProviderError):
            raise ProviderContractValidationError("error must be an AIProviderError when present")

        if self.status is ProviderExecutionStatus.SUCCESS:
            if self.error is not None:
                raise ProviderContractValidationError("a SUCCESS result must not carry an error")
            if self.content is None:
                raise ProviderContractValidationError("a SUCCESS result must carry content")
        elif self.status in (ProviderExecutionStatus.FAILED, ProviderExecutionStatus.UNAVAILABLE):
            if self.error is None:
                raise ProviderContractValidationError(
                    f"a {self.status.value.upper()} result must carry an error"
                )
            if self.content is not None:
                raise ProviderContractValidationError(
                    f"a {self.status.value.upper()} result must not carry content"
                )
        elif self.status is ProviderExecutionStatus.SKIPPED and (
            self.content is not None or self.error is not None
        ):
            raise ProviderContractValidationError(
                "a SKIPPED result must not carry content or an error"
            )


__all__ = [
    "AIProviderResult",
    "AIProviderResultContent",
]
