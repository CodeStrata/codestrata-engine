"""Validation for anonymous installation identity records (Epic 10 Slice 10.2)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    is_uuid_v4,
)
from codestrata.telemetry.analytics.installation_identity_compatibility import (
    assert_identity_schema_compatible,
    migrate_identity_mapping,
)
from codestrata.telemetry.analytics.installation_identity_errors import (
    InstallationIdentityError,
    InstallationIdentityErrorCode,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID,
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION,
    CommunityAnonymousInstallationIdentityPolicy,
    default_installation_identity_policy,
)

_ALLOWED_KEYS = frozenset(
    {"installation_id", "policy_version", "schema_id", "schema_version"}
)


def parse_identity_mapping(payload: dict[str, Any]) -> AnonymousInstallationIdentity:
    migrated = migrate_identity_mapping(payload)
    if set(migrated.keys()) - _ALLOWED_KEYS:
        raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD)
    for required in ("installation_id", "schema_id", "schema_version", "policy_version"):
        if required not in migrated:
            raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD)
        if not isinstance(migrated[required], str) or not migrated[required]:
            raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD)

    assert_identity_schema_compatible(migrated["schema_version"])
    if migrated["schema_id"] != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID:
        raise InstallationIdentityError(InstallationIdentityErrorCode.UNSUPPORTED_SCHEMA)
    if migrated["policy_version"] != COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION:
        raise InstallationIdentityError(InstallationIdentityErrorCode.UNSUPPORTED_POLICY)

    raw_id = migrated["installation_id"]
    if not is_uuid_v4(raw_id):
        raise InstallationIdentityError(InstallationIdentityErrorCode.INVALID_IDENTIFIER)
    canonical = str(uuid.UUID(raw_id))
    return AnonymousInstallationIdentity(
        installation_id=canonical,
        schema_id=COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID,
        schema_version=COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION,
        policy_version=COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION,
    )


def parse_identity_bytes(raw: bytes) -> AnonymousInstallationIdentity:
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD) from None
    if not isinstance(payload, dict):
        raise InstallationIdentityError(InstallationIdentityErrorCode.CORRUPT_RECORD)
    return parse_identity_mapping(payload)


def validate_identity_record(
    record: AnonymousInstallationIdentity,
    *,
    policy: CommunityAnonymousInstallationIdentityPolicy | None = None,
) -> AnonymousInstallationIdentity:
    active = policy or default_installation_identity_policy()
    active.validate()
    return parse_identity_mapping(record.to_stable_dict())


__all__ = [
    "parse_identity_bytes",
    "parse_identity_mapping",
    "validate_identity_record",
]
