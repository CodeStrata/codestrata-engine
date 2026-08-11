"""Installation identity schema compatibility (Epic 10 Slice 10.2).

Independent from analytics schema and telemetry runtime schema. Current
supported identity schema version: 1.0. Migration framework is forward-ready
but performs no transforms for 1.0.
"""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION,
)

_COMPATIBLE_SCHEMA_VERSIONS: frozenset[str] = frozenset(
    {COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION}
)


class InstallationIdentityCompatibilityError(InstallationIdentityError):
    """Raised when an identity schema version is unsupported."""

    def __init__(self) -> None:
        super().__init__(InstallationIdentityErrorCode.UNSUPPORTED_SCHEMA)


def compatible_identity_schema_versions() -> frozenset[str]:
    return _COMPATIBLE_SCHEMA_VERSIONS


def assert_identity_schema_compatible(schema_version: str) -> None:
    if schema_version not in _COMPATIBLE_SCHEMA_VERSIONS:
        raise InstallationIdentityCompatibilityError()


def migrate_identity_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Future-compatible migration hook.

    Schema 1.0 requires no transformation. Unsupported versions raise.
    """

    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD)
    assert_identity_schema_compatible(version)
    return dict(payload)


__all__ = [
    "InstallationIdentityCompatibilityError",
    "assert_identity_schema_compatible",
    "compatible_identity_schema_versions",
    "migrate_identity_mapping",
]
