"""Anonymous installation identity model, generation, and lifecycle (Epic 10 Slice 10.2).

Local anonymous continuity only. Not customer identity, authentication,
licensing, or telemetry consent. Analytics collection remains disabled —
this module does not transmit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codestrata.telemetry.analytics.installation_identity_diagnostics import (
    InstallationIdentityDiagnostics,
    empty_installation_identity_diagnostics,
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


def is_uuid_v4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4


def generate_anonymous_installation_id() -> str:
    """Return a fresh random UUID v4 — never derived from machine properties."""

    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class AnonymousInstallationIdentity:
    """Versioned anonymous installation identity record."""

    installation_id: str
    schema_id: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_ID
    schema_version: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION
    policy_version: str = COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "installation_id": self.installation_id,
            "policy_version": self.policy_version,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
        }


def new_anonymous_installation_identity() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(installation_id=generate_anonymous_installation_id())


def load_anonymous_installation_identity(
    *,
    home: Path | None = None,
    policy: CommunityAnonymousInstallationIdentityPolicy | None = None,
) -> AnonymousInstallationIdentity | None:
    """Load and validate a persisted identity. Returns None when absent.

    Raises InstallationIdentityError on corruption / unsupported versions.
    Does not create or recover.
    """

    from codestrata.telemetry.analytics.installation_identity_storage import (
        installation_identity_path,
        read_identity_bytes,
    )
    from codestrata.telemetry.analytics.installation_identity_validation import (
        parse_identity_bytes,
    )

    active = policy or default_installation_identity_policy()
    active.validate()
    path = installation_identity_path(home=home, policy=active)
    raw = read_identity_bytes(path=path)
    if raw is None:
        return None
    return parse_identity_bytes(raw)


def ensure_anonymous_installation_identity(
    *,
    home: Path | None = None,
    policy: CommunityAnonymousInstallationIdentityPolicy | None = None,
) -> tuple[AnonymousInstallationIdentity, bool, bool]:
    """Return ``(identity, created, recovered)``.

    Generate once when absent. Reuse thereafter. Never regenerate a valid
    identity automatically. On corruption, create a fresh identity only when
    ``policy.recover_on_corruption`` is true.
    """

    from codestrata.telemetry.analytics.installation_identity_storage import (
        ensure_identity_home,
        installation_identity_path,
        read_identity_bytes,
        write_identity_atomic,
    )
    from codestrata.telemetry.analytics.installation_identity_validation import (
        parse_identity_bytes,
    )

    active = policy or default_installation_identity_policy()
    active.validate()
    ensure_identity_home(home=home)
    path = installation_identity_path(home=home, policy=active)
    raw = read_identity_bytes(path=path)

    if raw is None:
        record = new_anonymous_installation_identity()
        write_identity_atomic(record, path=path)
        return record, True, False

    try:
        return parse_identity_bytes(raw), False, False
    except InstallationIdentityError:
        if not active.recover_on_corruption:
            raise InstallationIdentityError(
                InstallationIdentityErrorCode.RECOVERY_DISABLED
            ) from None
        record = new_anonymous_installation_identity()
        write_identity_atomic(record, path=path)
        return record, True, True


def diagnose_anonymous_installation_identity(
    *,
    home: Path | None = None,
    policy: CommunityAnonymousInstallationIdentityPolicy | None = None,
) -> InstallationIdentityDiagnostics:
    """Bounded diagnostics — never includes identifier values or paths."""

    active = policy or default_installation_identity_policy()
    base = empty_installation_identity_diagnostics(limitation_codes=active.limitations)
    try:
        loaded = load_anonymous_installation_identity(home=home, policy=active)
    except InstallationIdentityError as error:
        return InstallationIdentityDiagnostics(
            policy_version=base.policy_version,
            schema_version=base.schema_version,
            identity_present=True,
            identity_valid=False,
            created=False,
            recovered=False,
            transmission_allowed=False,
            telemetry_consent_coupled=False,
            last_error_code=error.code.value,
            limitation_codes=base.limitation_codes,
        )
    if loaded is None:
        return base
    return InstallationIdentityDiagnostics(
        policy_version=base.policy_version,
        schema_version=base.schema_version,
        identity_present=True,
        identity_valid=True,
        created=False,
        recovered=False,
        transmission_allowed=False,
        telemetry_consent_coupled=False,
        last_error_code=None,
        limitation_codes=base.limitation_codes,
    )


__all__ = [
    "AnonymousInstallationIdentity",
    "diagnose_anonymous_installation_identity",
    "ensure_anonymous_installation_identity",
    "generate_anonymous_installation_id",
    "is_uuid_v4",
    "load_anonymous_installation_identity",
    "new_anonymous_installation_identity",
]
