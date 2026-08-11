"""Contract version value object and support-checking helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError
from codestrata.ai.provider_contracts.policy import CONTRACT_VERSION

_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

# Slice 11.2 supports exactly one contract version. Future slices may extend
# this to a tuple of accepted versions with an explicit migration note.
SUPPORTED_CONTRACT_VERSIONS: tuple[str, ...] = (CONTRACT_VERSION,)


def is_supported_contract_version(value: str) -> bool:
    return value in SUPPORTED_CONTRACT_VERSIONS


def validate_contract_version(value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.match(value):
        raise ProviderContractValidationError(
            f"contract_version must match '<major>.<minor>', got {value!r}"
        )
    if not is_supported_contract_version(value):
        raise ProviderContractValidationError(
            f"unsupported contract_version {value!r}; supported: {SUPPORTED_CONTRACT_VERSIONS}"
        )


@dataclass(frozen=True, slots=True)
class ContractVersion:
    """A validated contract version string."""

    value: str

    def __post_init__(self) -> None:
        validate_contract_version(self.value)

    def __str__(self) -> str:
        return self.value


CURRENT_CONTRACT_VERSION = ContractVersion(CONTRACT_VERSION)


__all__ = [
    "CURRENT_CONTRACT_VERSION",
    "SUPPORTED_CONTRACT_VERSIONS",
    "ContractVersion",
    "is_supported_contract_version",
    "validate_contract_version",
]
