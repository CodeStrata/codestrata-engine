"""Schema version value object for provider capability descriptors/profiles.

A distinct version namespace from ``versions.CURRENT_CONTRACT_VERSION``
(Slice 11.2), ``configuration_compatibility.SUPPORTED_CONFIGURATION_VERSIONS``
(Slice 11.3), and ``execution_compatibility.SUPPORTED_EXECUTION_VERSIONS``
(Slice 11.4), even though all four currently happen to equal ``"1.0"``.
``ProviderCapabilityProfile.schema_version`` is the only field that reads
this module.
"""

from __future__ import annotations

import re

from codestrata.ai.provider_contracts.errors import ProviderContractValidationError

_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")

CURRENT_CAPABILITY_SCHEMA_VERSION = "1.0"

SUPPORTED_CAPABILITY_SCHEMA_VERSIONS: tuple[str, ...] = (CURRENT_CAPABILITY_SCHEMA_VERSION,)


def is_supported_capability_schema_version(value: str) -> bool:
    return value in SUPPORTED_CAPABILITY_SCHEMA_VERSIONS


def validate_capability_schema_version(value: str) -> None:
    if not isinstance(value, str) or not _VERSION_PATTERN.match(value):
        raise ProviderContractValidationError(
            f"schema_version must match '<major>.<minor>', got {value!r}"
        )
    if not is_supported_capability_schema_version(value):
        raise ProviderContractValidationError(
            f"unsupported schema_version {value!r}; supported: "
            f"{SUPPORTED_CAPABILITY_SCHEMA_VERSIONS}"
        )


__all__ = [
    "CURRENT_CAPABILITY_SCHEMA_VERSION",
    "SUPPORTED_CAPABILITY_SCHEMA_VERSIONS",
    "is_supported_capability_schema_version",
    "validate_capability_schema_version",
]
